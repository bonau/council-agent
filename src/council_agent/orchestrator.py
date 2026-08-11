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
from council_agent.crews.execution_tools import build_execution_tools
from council_agent.crews.planning import build_planning_crew, run_planning
from council_agent.crews.verification import build_verification_crew, run_verification
from council_agent.llm.openrouter import OpenRouterCredential, make_llm
from council_agent.sandbox.config import is_sandbox_initialized
from council_agent.sandbox.session import SessionManager
from council_agent.security import (
    AuditLogger,
    AuthenticationBinding,
    AuthenticationManager,
    ConfirmFn,
    ConfirmMode,
    ConfirmationPolicy,
    Principal,
    PrincipalResolver,
    SecurityContext,
    ServiceStepUpProvider,
    TrustGrantStore,
    TrustStoreError,
    TrustTier,
    authentication_audit_sink,
    default_audit_events_path,
    load_policy_file,
    parse_trust_tier,
    pipeline_attempt,
    principal_may_select_tier2,
    security_context,
    tier_selection_requires_step_up,
)
from council_agent.tools import ToolCallTracker
from council_agent.types import (
    AttemptKind,
    CouncilAttempt,
    CouncilResult,
    CouncilStopReason,
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
    *,
    enable_tools: bool = True,
) -> Crew:
    role = preset.escalation
    tools = build_execution_tools() if enable_tools else []
    agent = Agent(
        role="Escalation Specialist",
        goal="Resolve difficult issues and deliver a corrected result",
        backstory=ESCALATION_BACKSTORY,
        llm=make_llm(role.model, role.temperature, provider_credential),
        tools=tools,
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
    *,
    tracker: ToolCallTracker | None = None,
    attempt_id: str | None = None,
) -> ExecutionResult:
    summary_offset = len(tracker.summaries) if tracker is not None else 0
    result = crew.kickoff(
        inputs={
            "prompt": prompt,
            "steps": _format_steps(plan),
            "execution": execution.raw,
            "issues": _format_issues(verdict),
            "summary": verdict.summary,
        }
    )
    summaries = (
        list(tracker.summaries[summary_offset:]) if tracker is not None else []
    )
    return ExecutionResult(
        raw=crew_output_text(result),
        tool_summaries=summaries,
        attempt_id=attempt_id,
    )


def _bind_attempt(
    execution: ExecutionResult,
    attempt_id: str,
) -> ExecutionResult:
    """Normalize patched/legacy runners while rejecting conflicting evidence."""
    if execution.attempt_id not in {None, attempt_id}:
        raise ValueError("execution returned a conflicting pipeline attempt ID")
    execution.attempt_id = attempt_id
    return execution


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
    trust_tier: TrustTier | int | str = TrustTier.TIER_1,
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
    selected_tier = parse_trust_tier(trust_tier)

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

    if tier_selection_requires_step_up(selected_tier):
        if not principal_may_select_tier2(principal.scopes):
            raise ValueError(
                "Trust Tier 2 requires principal scope high-risk:manage"
            )
        if (
            authentication_manager is None
            or step_up_provider is None
            or authentication_verifier is None
        ):
            raise ValueError(
                "Trust Tier 2 requires fresh step-up authentication "
                "(configure COUNCIL_AUTH_SECRET)"
            )
        binding = AuthenticationBinding.for_action(
            principal,
            workspace_root,
            runtime_session_id,
            "select_trust_tier",
            {"trust_tier": int(selected_tier)},
        )
        token = step_up_provider(binding)
        if token is None:
            raise ValueError(
                "Trust Tier 2 step-up authentication is missing or invalid"
            )
        auth_decision = authentication_manager.consume_step_up(token, binding)
        if not auth_decision.allowed:
            raise ValueError(
                "Trust Tier 2 step-up authentication is missing or invalid"
            )

    trust_grant_store: TrustGrantStore | None
    try:
        trust_grant_store = TrustGrantStore(workspace_root)
    except TrustStoreError:
        trust_grant_store = None

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
            trust_tier=selected_tier,
            trust_grant_store=trust_grant_store,
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
            attempts: list[CouncilAttempt] = []
            initial_attempt_id = str(uuid.uuid4())
            with pipeline_attempt(initial_attempt_id):
                execution = _bind_attempt(
                    run_execution(
                        execution_crew,
                        prompt,
                        plan,
                        tracker=tracker,
                        attempt_id=initial_attempt_id,
                    ),
                    initial_attempt_id,
                )
                verdict = run_verification(
                    verification_crew,
                    prompt,
                    plan,
                    execution,
                )
            attempts.append(
                CouncilAttempt(
                    attempt_id=initial_attempt_id,
                    sequence=1,
                    kind=AttemptKind.INITIAL,
                    execution=execution,
                    verdict=verdict,
                )
            )

            escalation_crew = None
            retries = 0
            while (
                verdict.status == VerdictStatus.FAIL
                and retries < preset.max_retries
            ):
                if escalation_crew is None:
                    escalation_crew = build_escalation_crew(
                        preset,
                        provider_credential,
                    )
                    if verbose:
                        escalation_crew.verbose = True
                retries += 1
                attempt_id = str(uuid.uuid4())
                with pipeline_attempt(attempt_id):
                    execution = _bind_attempt(
                        run_escalation(
                            escalation_crew,
                            prompt,
                            plan,
                            execution,
                            verdict,
                            tracker=tracker,
                            attempt_id=attempt_id,
                        ),
                        attempt_id,
                    )
                    verdict = run_verification(
                        verification_crew,
                        prompt,
                        plan,
                        execution,
                    )
                attempts.append(
                    CouncilAttempt(
                        attempt_id=attempt_id,
                        sequence=len(attempts) + 1,
                        kind=AttemptKind.ESCALATION,
                        execution=execution,
                        verdict=verdict,
                    )
                )

            if verdict.status is VerdictStatus.PASS:
                stop_reason = CouncilStopReason.PASSED
            elif preset.max_retries == 0:
                stop_reason = CouncilStopReason.RETRIES_DISABLED
            else:
                stop_reason = CouncilStopReason.RETRIES_EXHAUSTED

            final_attempt = attempts[-1]
            return CouncilResult(
                prompt=prompt,
                plan=plan,
                execution=final_attempt.execution,
                verdict=final_attempt.verdict,
                escalated=len(attempts) > 1,
                final_output=final_attempt.execution.raw,
                attempts=attempts,
                final_attempt_id=final_attempt.attempt_id,
                stop_reason=stop_reason,
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
