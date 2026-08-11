"""Verification crew: validate execution against the plan."""

from __future__ import annotations

import json

from crewai import Agent, Crew, Process, Task

from council_agent.config.presets import Preset
from council_agent.crews.base import crew_output_text, extract_json_block
from council_agent.llm.openrouter import OpenRouterCredential, make_llm
from council_agent.types import (
    ExecutionResult,
    PlanArtifact,
    ToolCallSummary,
    VerdictStatus,
    VerificationVerdict,
)

VERIFICATION_BACKSTORY = (
    "You are a rigorous verifier. Compare deliverables against the plan and "
    "success criteria. Be objective and specific about any gaps."
)

VERIFICATION_TASK_DESCRIPTION = """
Verify whether the execution result satisfies the plan and success criteria.

Original request:
{prompt}

Plan steps:
{steps}

Success criteria:
{success_criteria}

Execution result:
{execution}

Tool execution summaries (if any):
{tool_summaries}

When tool summaries include test results (run_tests), you MUST compare:
- test exit code (metadata.exit_code): 0 means tests passed
- passed / failed / skipped counts against the success criteria
- failure summaries in metadata.failures

If tests failed (non-zero exit code or failed > 0), status should be FAIL unless
the success criteria explicitly allow partial failure.

Respond with a JSON object only (no extra text) using this schema:
{{
  "status": "PASS" or "FAIL",
  "summary": "brief overall assessment",
  "issues": ["issue 1", ...]
}}
"""


def _format_tool_summaries(summaries: list[ToolCallSummary]) -> str:
    if not summaries:
        return "- (no tool calls recorded)"
    lines: list[str] = []
    for s in summaries:
        meta = s.metadata
        parts = [f"- {s.tool}: success={s.success}"]
        if "exit_code" in meta:
            parts.append(f"exit_code={meta['exit_code']}")
        for key in ("passed", "failed", "skipped"):
            if key in meta:
                parts.append(f"{key}={meta[key]}")
        if meta.get("failures"):
            parts.append(f"failures={meta['failures']}")
        if s.error:
            parts.append(f"error={s.error!r}")
        lines.append(", ".join(parts))
    return "\n".join(lines)


def build_verification_crew(
    preset: Preset,
    provider_credential: OpenRouterCredential,
) -> Crew:
    role = preset.verification
    agent = Agent(
        role="Quality Verifier",
        goal="Validate execution output against the plan and success criteria",
        backstory=VERIFICATION_BACKSTORY,
        llm=make_llm(role.model, role.temperature, provider_credential),
        verbose=False,
    )
    task = Task(
        description=VERIFICATION_TASK_DESCRIPTION,
        expected_output='A JSON object with status ("PASS" or "FAIL"), summary, and issues',
        agent=agent,
    )
    return Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=False)


def run_verification(
    crew: Crew,
    prompt: str,
    plan: PlanArtifact,
    execution: ExecutionResult,
) -> VerificationVerdict:
    steps = "\n".join(f"- {s}" for s in plan.steps) or "- (no steps)"
    criteria = "\n".join(f"- {c}" for c in plan.success_criteria) or "- (none)"
    summaries = execution.tool_summaries or []
    result = crew.kickoff(
        inputs={
            "prompt": prompt,
            "steps": steps,
            "success_criteria": criteria,
            "execution": execution.raw,
            "tool_summaries": _format_tool_summaries(summaries),
        }
    )
    raw = crew_output_text(result)
    try:
        data = extract_json_block(raw)
        status_str = str(data.get("status", "FAIL")).upper()
        status = VerdictStatus.PASS if status_str == "PASS" else VerdictStatus.FAIL
        return VerificationVerdict(
            status=status,
            raw=raw,
            issues=[str(i) for i in data.get("issues", [])],
            summary=str(data.get("summary", "")),
        )
    except (ValueError, json.JSONDecodeError):
        return VerificationVerdict(
            status=VerdictStatus.FAIL,
            raw=raw,
            issues=["Could not parse verification output"],
            summary="Verification output was not valid JSON",
        )
