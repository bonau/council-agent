"""Orchestrator: wire planning, execution, verification, and escalation."""

from __future__ import annotations

from crewai import Agent, Crew, Process, Task

from council_agent.config.presets import Preset
from council_agent.crews.execution import build_execution_crew, run_execution
from council_agent.crews.planning import build_planning_crew, run_planning
from council_agent.crews.verification import build_verification_crew, run_verification
from council_agent.crews.base import crew_output_text
from council_agent.llm.openrouter import make_llm
from council_agent.types import (
    CouncilResult,
    ExecutionResult,
    PlanArtifact,
    VerdictStatus,
    VerificationVerdict,
)

ESCALATION_BACKSTORY = (
    "You are a senior specialist called in when verification fails. "
    "Fix the identified issues and produce an improved final deliverable."
)

ESCALATION_TASK_DESCRIPTION = """
The verification step found issues with the previous execution. Fix them and
produce an improved deliverable.

Original request:
{prompt}

Plan steps:
{steps}

Previous execution:
{execution}

Verification issues:
{issues}

Verification summary:
{summary}

Address every issue and deliver the corrected, complete result.
"""


def _format_steps(plan: PlanArtifact) -> str:
    return "\n".join(f"- {s}" for s in plan.steps) or "- (no steps)"


def _format_issues(verdict: VerificationVerdict) -> str:
    return "\n".join(f"- {i}" for i in verdict.issues) or "- (none listed)"


def build_escalation_crew(preset: Preset, api_key: str) -> Crew:
    role = preset.escalation
    agent = Agent(
        role="Escalation Specialist",
        goal="Resolve difficult issues and deliver a corrected result",
        backstory=ESCALATION_BACKSTORY,
        llm=make_llm(role.model, role.temperature, api_key),
        verbose=False,
    )
    task = Task(
        description=ESCALATION_TASK_DESCRIPTION,
        expected_output="A corrected, complete deliverable addressing all verification issues",
        agent=agent,
    )
    return Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=False)


def run_escalation(
    crew: Crew,
    prompt: str,
    plan: PlanArtifact,
    execution: ExecutionResult,
    verdict: VerificationVerdict,
) -> ExecutionResult:
    result = crew.kickoff(
        inputs={
            "prompt": prompt,
            "steps": _format_steps(plan),
            "execution": execution.raw,
            "issues": _format_issues(verdict),
            "summary": verdict.summary,
        }
    )
    return ExecutionResult(raw=crew_output_text(result))


def run_council(
    prompt: str,
    preset: Preset,
    api_key: str,
    *,
    verbose: bool = False,
) -> CouncilResult:
    """Run the full three-phase council pipeline with optional escalation."""
    planning_crew = build_planning_crew(preset, api_key)
    execution_crew = build_execution_crew(preset, api_key)
    verification_crew = build_verification_crew(preset, api_key)

    if verbose:
        planning_crew.verbose = True
        execution_crew.verbose = True
        verification_crew.verbose = True

    plan = run_planning(planning_crew, prompt)
    execution = run_execution(execution_crew, prompt, plan)
    verdict = run_verification(verification_crew, prompt, plan, execution)

    escalated = False
    final_output = execution.raw

    if verdict.status == VerdictStatus.FAIL and preset.max_retries > 0:
        escalation_crew = build_escalation_crew(preset, api_key)
        if verbose:
            escalation_crew.verbose = True
        execution = run_escalation(
            escalation_crew, prompt, plan, execution, verdict
        )
        escalated = True
        final_output = execution.raw

    return CouncilResult(
        prompt=prompt,
        plan=plan,
        execution=execution,
        verdict=verdict,
        escalated=escalated,
        final_output=final_output,
    )
