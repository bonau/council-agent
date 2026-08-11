"""Orchestrator: wire planning, execution, verification, and escalation."""

from __future__ import annotations

from pathlib import Path

from crewai import Agent, Crew, Process, Task

from council_agent.config.presets import Preset, get_effective_max_tool_calls
from council_agent.config.settings import get_settings
from council_agent.crews.base import crew_output_text
from council_agent.crews.execution import build_execution_crew, run_execution
from council_agent.crews.planning import build_planning_crew, run_planning
from council_agent.crews.verification import build_verification_crew, run_verification
from council_agent.llm.openrouter import make_llm
from council_agent.sandbox.config import is_sandbox_initialized
from council_agent.sandbox.session import SessionManager
from council_agent.security import (
    AuditLogger,
    ConfirmFn,
    ConfirmMode,
    ConfirmationPolicy,
    SecurityContext,
    default_audit_events_path,
    load_policy_file,
    security_context,
)
from council_agent.tools import ToolCallTracker
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


def _resolve_session_project(
    workspace_root: Path,
    project_root: Path | None,
) -> Path | None:
    """Return a project root that has `.council/`, or None if sandbox is inactive."""
    candidates: list[Path] = []
    if project_root is not None:
        candidates.append(Path(project_root).expanduser().resolve())
    candidates.append(Path(workspace_root).expanduser().resolve())
    cwd = Path.cwd().resolve()
    if cwd not in candidates:
        candidates.append(cwd)

    for candidate in candidates:
        if is_sandbox_initialized(candidate):
            return candidate
    return None


def _resolve_policy_root(
    workspace_root: Path,
    project_root: Path | None,
    session_project: Path | None,
) -> Path:
    """Prefer sandbox project root, then explicit project_root, then workspace."""
    if session_project is not None:
        return session_project
    if project_root is not None:
        return Path(project_root).expanduser().resolve()
    return Path(workspace_root).expanduser().resolve()


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
    project_root: Path | str | None = None,
    confirm_mode: ConfirmMode = ConfirmMode.COMPAT,
    confirm_fn: ConfirmFn | None = None,
) -> CouncilResult:
    """Run the full three-phase council pipeline with optional escalation."""
    settings = get_settings()
    workspace_root = Path(settings.council_workspace_root).resolve()
    session_project = _resolve_session_project(
        workspace_root,
        Path(project_root) if project_root is not None else None,
    )

    policy_root = _resolve_policy_root(
        workspace_root,
        Path(project_root) if project_root is not None else None,
        session_project,
    )
    # Fail fast on invalid policy before session/crews start.
    loaded_policy = load_policy_file(policy_root)

    session: SessionManager | None = None
    if session_project is not None:
        session = SessionManager.create(
            prompt=prompt,
            preset=preset.name,
            workspace_root=workspace_root,
            project_root=session_project,
        )

    tracker = ToolCallTracker(max_tool_calls=get_effective_max_tool_calls(preset))

    audit_logger = None
    if session is not None and session_project is not None:
        audit_logger = AuditLogger(
            default_audit_events_path(session_project),
            session_id=session.meta.session_id,
        )

    context = SecurityContext.create(
        workspace_root,
        policy=loaded_policy,
        confirmation=ConfirmationPolicy(
            mode=confirm_mode,
            confirm_fn=confirm_fn,
        ),
        tracker=tracker,
        session=session,
        audit_logger=audit_logger,
    )

    session_status = "completed"
    try:
        with security_context(context):
            planning_crew = build_planning_crew(preset, api_key)
            execution_crew = build_execution_crew(
                preset,
                api_key,
                tracker=tracker,
                session=session,
            )
            verification_crew = build_verification_crew(preset, api_key)

            if verbose:
                planning_crew.verbose = True
                execution_crew.verbose = True
                verification_crew.verbose = True

            plan = run_planning(planning_crew, prompt)
            execution = run_execution(
                execution_crew, prompt, plan, tracker=tracker
            )
            verdict = run_verification(
                verification_crew,
                prompt,
                plan,
                execution,
            )

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
    except Exception:
        session_status = "failed"
        raise
    finally:
        if session is not None:
            # Keep count in sync if tools logged via tracker but finalize late.
            session.meta.tool_call_count = max(
                session.meta.tool_call_count, len(tracker.summaries)
            )
            session.finalize(status=session_status)
