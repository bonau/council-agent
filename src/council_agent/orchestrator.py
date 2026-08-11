"""Orchestrator: wire planning, execution, verification, and escalation."""

from __future__ import annotations

import uuid
from pathlib import Path

from crewai import Agent, Crew, Process, Task
from pydantic import SecretStr

from council_agent.config.presets import Preset, get_effective_max_tool_calls
from council_agent.config.settings import get_settings
from council_agent.crews.base import crew_output_text
from council_agent.crews.execution import build_execution_crew, run_execution
from council_agent.crews.planning import build_planning_crew, run_planning
from council_agent.crews.verification import build_verification_crew, run_verification
from council_agent.llm.openrouter import OpenRouterCredential, make_llm
from council_agent.sandbox.config import is_sandbox_initialized
from council_agent.sandbox.session import SessionManager
from council_agent.security import (
    AuditLogger,
    AuthenticationManager,
    ConfirmFn,
    ConfirmMode,
    ConfirmationPolicy,
    Principal,
    PrincipalResolver,
    SecurityContext,
    ServiceStepUpProvider,
    authentication_audit_sink,
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


def build_escalation_crew(
    preset: Preset,
    provider_credential: OpenRouterCredential,
) -> Crew:
    role = preset.escalation
    agent = Agent(
        role="Escalation Specialist",
        goal="Resolve difficult issues and deliver a corrected result",
        backstory=ESCALATION_BACKSTORY,
        llm=make_llm(role.model, role.temperature, provider_credential),
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
    provider_credential: OpenRouterCredential,
    principal: Principal,
    *,
    verbose: bool = False,
    project_root: Path | str | None = None,
    confirm_mode: ConfirmMode = ConfirmMode.COMPAT,
    confirm_fn: ConfirmFn | None = None,
    principal_resolver: PrincipalResolver | None = None,
    authentication_verifier: SecretStr | None = None,
) -> CouncilResult:
    """Run the full three-phase council pipeline with optional escalation."""
    if not isinstance(provider_credential, OpenRouterCredential):
        raise TypeError("provider_credential must be an OpenRouterCredential")
    if not isinstance(principal, Principal):
        raise TypeError("principal must be a Council Principal")
    try:
        principal.__post_init__()
    except ValueError as exc:
        raise ValueError("principal is invalid") from exc
    if authentication_verifier is not None:
        if not isinstance(authentication_verifier, SecretStr):
            raise TypeError("authentication_verifier must be a SecretStr")
        if not authentication_verifier.get_secret_value():
            raise ValueError("authentication_verifier must be non-empty")

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
    request_id = str(uuid.uuid4())
    runtime_session_id = (
        session.meta.session_id if session is not None else str(uuid.uuid4())
    )

    audit_logger = None
    if session is not None and session_project is not None:
        audit_logger = AuditLogger(
            default_audit_events_path(session_project),
            session_id=runtime_session_id,
        )

    authentication_manager = None
    step_up_provider = None
    if authentication_verifier is not None:
        authentication_manager = AuthenticationManager(
            authentication_verifier,
            event_sink=authentication_audit_sink(
                audit_logger,
                request_id=request_id,
                session_id=runtime_session_id,
            ),
        )
        step_up_provider = ServiceStepUpProvider(
            authentication_manager,
            authentication_verifier,
        )

    session_status = "completed"
    try:
        context = SecurityContext.create(
            workspace_root,
            request_id=request_id,
            session_id=runtime_session_id,
            policy=loaded_policy,
            confirmation=ConfirmationPolicy(
                mode=confirm_mode,
                confirm_fn=confirm_fn,
            ),
            tracker=tracker,
            principal=principal,
            principal_resolver=principal_resolver,
            authentication_manager=authentication_manager,
            step_up_provider=step_up_provider,
            require_high_risk_step_up=True,
            session=session,
            audit_logger=audit_logger,
        )
        with security_context(context):
            planning_crew = build_planning_crew(preset, provider_credential)
            execution_crew = build_execution_crew(
                preset,
                provider_credential,
            )
            verification_crew = build_verification_crew(
                preset,
                provider_credential,
            )

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
                escalation_crew = build_escalation_crew(
                    preset,
                    provider_credential,
                )
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
        if authentication_manager is not None:
            authentication_manager.revoke()
        if session is not None:
            # Keep count in sync if tools logged via tracker but finalize late.
            session.meta.tool_call_count = max(
                session.meta.tool_call_count, len(tracker.summaries)
            )
            session.finalize(status=session_status)
