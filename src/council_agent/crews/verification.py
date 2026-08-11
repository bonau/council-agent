"""Verification crew: validate execution against the plan."""

from __future__ import annotations

import json
import re

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

The runtime also applies a deterministic evidence gate after your response.
When the request or success criteria require product tools or passing tests,
missing, malformed, failed, or cross-attempt evidence cannot be PASS.

Respond with a JSON object only (no extra text) using this schema:
{{
  "status": "PASS" or "FAIL",
  "summary": "brief overall assessment",
  "issues": ["issue 1", ...]
}}
"""

_PRODUCT_TOOLS = frozenset(
    {
        "read_file",
        "write_file",
        "list_dir",
        "delete_file",
        "run_command",
        "run_tests",
    }
)
_TEST_EVIDENCE_PATTERNS = (
    re.compile(r"\b(?:pytest|run_tests)\b", re.IGNORECASE),
    re.compile(
        r"\b(?:tests?|test suite)\b.{0,40}\b(?:pass|passing|passed|green|run)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:pass|passing|passed|run)\b.{0,40}\b(?:tests?|test suite)\b",
        re.IGNORECASE,
    ),
    re.compile(r"(?:測試|pytest).{0,24}(?:通過|全綠|執行|成功)"),
)
_OBSERVABLE_EVIDENCE_PATTERNS = (
    re.compile(
        r"\b(?:create|write|modify|update|delete|read|list|run|execute)\b"
        r".{0,40}\b(?:file|directory|command)\b",
        re.IGNORECASE,
    ),
    re.compile(r"(?:建立|寫入|修改|更新|刪除|讀取|列出|執行).{0,24}(?:檔案|目錄|指令)"),
)


def _evidence_text(prompt: str, plan: PlanArtifact) -> str:
    return "\n".join(
        [prompt, *plan.steps, *plan.success_criteria]
    )


def _required_evidence(
    prompt: str,
    plan: PlanArtifact,
) -> tuple[set[str], bool]:
    text = _evidence_text(prompt, plan)
    required_tools = {tool for tool in _PRODUCT_TOOLS if tool in text}
    tests_required = any(pattern.search(text) for pattern in _TEST_EVIDENCE_PATTERNS)
    if tests_required:
        required_tools.add("run_tests")
    any_tool_required = (
        not required_tools
        and any(pattern.search(text) for pattern in _OBSERVABLE_EVIDENCE_PATTERNS)
    )
    return required_tools, any_tool_required


def validate_required_evidence(
    prompt: str,
    plan: PlanArtifact,
    execution: ExecutionResult,
) -> list[str]:
    """Return deterministic reasons the current attempt cannot be PASS."""
    summaries = execution.tool_summaries or []
    issues: list[str] = []

    if execution.attempt_id is not None:
        for summary in summaries:
            metadata = summary.metadata
            if metadata.get("pipeline_attempt_id") != execution.attempt_id:
                issues.append(
                    "Tool evidence does not belong to the current pipeline attempt"
                )
                continue
            missing_correlation = [
                key
                for key in ("request_id", "action_id", "decision", "trust_decision")
                if key not in metadata
            ]
            if missing_correlation:
                issues.append(
                    "Tool evidence is missing current-attempt correlation: "
                    + ", ".join(missing_correlation)
                )

    required_tools, any_tool_required = _required_evidence(prompt, plan)
    available_tools = {summary.tool for summary in summaries}
    for tool in sorted(required_tools - available_tools):
        issues.append(f"Required tool evidence is missing: {tool}")
    if any_tool_required and not summaries:
        issues.append("Required product-tool evidence is missing")

    if "run_tests" in required_tools and "run_tests" in available_tools:
        latest_test = next(
            summary for summary in reversed(summaries) if summary.tool == "run_tests"
        )
        metadata = latest_test.metadata
        missing_test_fields = [
            key for key in ("exit_code", "failed") if key not in metadata
        ]
        if missing_test_fields:
            issues.append(
                "Required test evidence is incomplete: "
                + ", ".join(missing_test_fields)
            )
        elif (
            not latest_test.success
            or metadata["exit_code"] != 0
            or metadata["failed"] != 0
        ):
            issues.append("Required test evidence did not pass")

    return list(dict.fromkeys(issues))


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
        issues = [str(i) for i in data.get("issues", [])]
        evidence_issues = validate_required_evidence(
            prompt,
            plan,
            execution,
        )
        if evidence_issues:
            status = VerdictStatus.FAIL
            issues.extend(evidence_issues)
        return VerificationVerdict(
            status=status,
            raw=raw,
            issues=list(dict.fromkeys(issues)),
            summary=str(data.get("summary", "")),
        )
    except (ValueError, json.JSONDecodeError):
        return VerificationVerdict(
            status=VerdictStatus.FAIL,
            raw=raw,
            issues=["Could not parse verification output"],
            summary="Verification output was not valid JSON",
        )
