"""Verification crew: validate execution against the plan."""

from __future__ import annotations

import json

from crewai import Agent, Crew, Process, Task

from council_agent.config.presets import Preset
from council_agent.crews.base import crew_output_text, extract_json_block
from council_agent.llm.openrouter import make_llm
from council_agent.types import (
    ExecutionResult,
    PlanArtifact,
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

Respond with a JSON object only (no extra text) using this schema:
{{
  "status": "PASS" or "FAIL",
  "summary": "brief overall assessment",
  "issues": ["issue 1", ...]
}}
"""


def build_verification_crew(preset: Preset, api_key: str) -> Crew:
    role = preset.verification
    agent = Agent(
        role="Quality Verifier",
        goal="Validate execution output against the plan and success criteria",
        backstory=VERIFICATION_BACKSTORY,
        llm=make_llm(role.model, role.temperature, api_key),
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
    result = crew.kickoff(
        inputs={
            "prompt": prompt,
            "steps": steps,
            "success_criteria": criteria,
            "execution": execution.raw,
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
