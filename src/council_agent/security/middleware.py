"""Mandatory policy middleware and request-scoped security context."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass, field, replace
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterator

from council_agent.sandbox.workspace import DEFAULT_DENIED_PATTERNS, WorkspaceGuard
from council_agent.security.audit import AuditLogger, AuditRecord
from council_agent.security.confirm import ConfirmationPolicy
from council_agent.security.policy import (
    CURRENT_POLICY_SCHEMA_VERSION,
    CouncilPolicy,
)
from council_agent.security.principal import (
    AuthorizationReason,
    Principal,
    PrincipalResolver,
    ScopeDecision,
    evaluate_principal_scopes,
    required_scopes_for_action,
)
from council_agent.tools.base import ToolResult, _err
from council_agent.tools.tracker import ToolCallTracker

if TYPE_CHECKING:
    from council_agent.sandbox.session import SessionManager

POLICY_VERSION_UNVERSIONED = "v0.9-unversioned"
POLICY_VERSION_BUILTIN = "builtin"
POLICY_VERSION_PROJECT_V1 = (
    f"project-policy/v{CURRENT_POLICY_SCHEMA_VERSION}"
)
SUPPORTED_TOOL_NAMES = frozenset(
    {
        "read_file",
        "write_file",
        "list_dir",
        "delete_file",
        "run_command",
        "run_tests",
    }
)


class SecurityContextReason(str, Enum):
    MISSING = "security_context_missing"
    CLOSED = "security_context_closed"
    INVALID = "security_context_invalid"
    ALREADY_ACTIVE = "security_context_already_active"


class SecurityContextError(RuntimeError):
    """A security context is missing, stale, or internally inconsistent."""

    def __init__(self, message: str, reason: SecurityContextReason) -> None:
        super().__init__(message)
        self.reason = reason


class _LeaseState(str, Enum):
    NEW = "new"
    ACTIVE = "active"
    CLOSED = "closed"


@dataclass
class _ContextLease:
    state: _LeaseState = _LeaseState.NEW

    def activate(self) -> None:
        if self.state is _LeaseState.CLOSED:
            raise SecurityContextError(
                "Security context has already been closed",
                SecurityContextReason.CLOSED,
            )
        if self.state is _LeaseState.ACTIVE:
            raise SecurityContextError(
                "Security context is already active",
                SecurityContextReason.ALREADY_ACTIVE,
            )
        self.state = _LeaseState.ACTIVE

    def require_active(self) -> None:
        if self.state is _LeaseState.CLOSED:
            raise SecurityContextError(
                "Security context has been closed",
                SecurityContextReason.CLOSED,
            )
        if self.state is not _LeaseState.ACTIVE:
            raise SecurityContextError(
                "Security context is not active",
                SecurityContextReason.INVALID,
            )

    def close(self) -> None:
        self.state = _LeaseState.CLOSED


@dataclass(frozen=True)
class SecurityContext:
    """One immutable snapshot used by every tool action in a product request."""

    request_id: str
    workspace: WorkspaceGuard
    policy: CouncilPolicy | None
    confirmation: ConfirmationPolicy
    tracker: ToolCallTracker
    principal: Principal | None = None
    principal_resolver: PrincipalResolver | None = field(
        default=None,
        repr=False,
        compare=False,
    )
    session_id: str | None = None
    session: SessionManager | None = None
    audit_logger: AuditLogger | None = None
    policy_version: str = POLICY_VERSION_BUILTIN
    _lease: _ContextLease = field(
        default_factory=_ContextLease,
        repr=False,
        compare=False,
    )

    @classmethod
    def create(
        cls,
        workspace_root: Path | str,
        *,
        request_id: str | None = None,
        session_id: str | None = None,
        policy: CouncilPolicy | None = None,
        confirmation: ConfirmationPolicy | None = None,
        tracker: ToolCallTracker | None = None,
        principal: Principal | None = None,
        principal_resolver: PrincipalResolver | None = None,
        session: SessionManager | None = None,
        audit_logger: AuditLogger | None = None,
    ) -> SecurityContext:
        """Build and validate one context snapshot for a product scope."""

        resolved_session_id = session_id
        if resolved_session_id is None and session is not None:
            resolved_session_id = session.meta.session_id
        if resolved_session_id is None and audit_logger is not None:
            resolved_session_id = audit_logger.session_id

        context = cls(
            request_id=request_id or str(uuid.uuid4()),
            workspace=_workspace_guard(Path(workspace_root), policy),
            policy=policy,
            confirmation=confirmation or ConfirmationPolicy(),
            tracker=tracker if tracker is not None else ToolCallTracker(),
            principal=principal,
            principal_resolver=principal_resolver,
            session_id=resolved_session_id,
            session=session,
            audit_logger=audit_logger,
            policy_version=_policy_version(policy),
        )
        context.validate(require_active=False)
        return context

    def validate(self, *, require_active: bool = True) -> None:
        """Reject malformed, mismatched, or stale context state."""

        if not self.request_id.strip():
            raise SecurityContextError(
                "Security context request_id must be non-empty",
                SecurityContextReason.INVALID,
            )
        if not self.policy_version.strip():
            raise SecurityContextError(
                "Security context policy_version must be non-empty",
                SecurityContextReason.INVALID,
            )
        expected_policy_version = _policy_version(self.policy)
        if self.policy_version != expected_policy_version:
            raise SecurityContextError(
                "Security context policy_version does not match policy snapshot",
                SecurityContextReason.INVALID,
            )
        if not isinstance(self.tracker, ToolCallTracker):
            raise SecurityContextError(
                "Security context tracker is invalid",
                SecurityContextReason.INVALID,
            )
        if self.principal is not None:
            if not isinstance(self.principal, Principal):
                raise SecurityContextError(
                    "Security context principal is invalid",
                    SecurityContextReason.INVALID,
                )
            try:
                self.principal.__post_init__()
            except ValueError as exc:
                raise SecurityContextError(
                    "Security context principal is invalid",
                    SecurityContextReason.INVALID,
                ) from exc
        if self.principal_resolver is not None:
            if not callable(self.principal_resolver):
                raise SecurityContextError(
                    "Security context principal resolver is invalid",
                    SecurityContextReason.INVALID,
                )
            if self.principal is None:
                raise SecurityContextError(
                    "Security context principal resolver requires a bound principal",
                    SecurityContextReason.INVALID,
                )
        if self.session is not None:
            session_workspace = Path(self.session.meta.workspace_root).resolve()
            if session_workspace != self.workspace.root:
                raise SecurityContextError(
                    "Security context session workspace does not match workspace guard",
                    SecurityContextReason.INVALID,
                )
            if self.session_id != self.session.meta.session_id:
                raise SecurityContextError(
                    "Security context session identity does not match session writer",
                    SecurityContextReason.INVALID,
                )
        if (
            self.audit_logger is not None
            and self.audit_logger.session_id is not None
            and self.audit_logger.session_id != self.session_id
        ):
            raise SecurityContextError(
                "Security context audit identity does not match session identity",
                SecurityContextReason.INVALID,
            )
        if require_active:
            self._lease.require_active()
        elif self._lease.state is _LeaseState.CLOSED:
            raise SecurityContextError(
                "Security context has been closed",
                SecurityContextReason.CLOSED,
            )


_ACTIVE_CONTEXT: ContextVar[SecurityContext | None] = ContextVar(
    "council_security_context",
    default=None,
)
_UNSET = object()


def _workspace_guard(
    workspace_root: Path | str,
    policy: CouncilPolicy | None,
) -> WorkspaceGuard:
    patterns = list(DEFAULT_DENIED_PATTERNS)
    if policy is not None:
        for pattern in policy.denied_paths:
            if pattern not in patterns:
                patterns.append(pattern)
    return WorkspaceGuard(Path(workspace_root), denied_patterns=tuple(patterns))


def _policy_version(policy: CouncilPolicy | None) -> str:
    if policy is None:
        return POLICY_VERSION_BUILTIN
    return f"project-policy/v{policy.schema_version}"


def get_security_context() -> SecurityContext | None:
    """Return the current context without synthesizing a default."""

    return _ACTIVE_CONTEXT.get()


def require_security_context() -> SecurityContext:
    """Return one validated active context or raise a diagnostic error."""

    context = get_security_context()
    if context is None:
        raise SecurityContextError(
            "No SecurityContext is installed",
            SecurityContextReason.MISSING,
        )
    context.validate(require_active=True)
    return context


def _set_security_context_view(
    *,
    policy: CouncilPolicy | None | object = _UNSET,
    confirmation: ConfirmationPolicy | object = _UNSET,
    audit_logger: AuditLogger | None | object = _UNSET,
) -> Token[SecurityContext | None] | None:
    """Derive one complete active view for legacy low-level context helpers."""

    current = get_security_context()
    if current is None:
        return None
    current.validate(require_active=True)

    updates: dict[str, Any] = {}
    if policy is not _UNSET:
        assert policy is None or isinstance(policy, CouncilPolicy)
        updates["policy"] = policy
        updates["workspace"] = _workspace_guard(current.workspace.root, policy)
        updates["policy_version"] = _policy_version(policy)
    if confirmation is not _UNSET:
        assert isinstance(confirmation, ConfirmationPolicy)
        updates["confirmation"] = confirmation
    if audit_logger is not _UNSET:
        assert audit_logger is None or isinstance(audit_logger, AuditLogger)
        updates["audit_logger"] = audit_logger

    derived = replace(current, **updates)
    derived.validate(require_active=True)
    return _ACTIVE_CONTEXT.set(derived)


def _reset_security_context_view(
    token: Token[SecurityContext | None] | None,
) -> None:
    if token is not None:
        _ACTIVE_CONTEXT.reset(token)


@contextmanager
def without_security_context() -> Iterator[None]:
    """Temporarily expose fail-closed missing-context behavior."""

    token = _ACTIVE_CONTEXT.set(None)
    try:
        yield
    finally:
        _ACTIVE_CONTEXT.reset(token)


@contextmanager
def security_context(context: SecurityContext) -> Iterator[SecurityContext]:
    """Install exactly one product security context and close it on exit."""

    current = get_security_context()
    if current is not None:
        try:
            current.validate(require_active=True)
        except SecurityContextError:
            pass
        else:
            raise SecurityContextError(
                "A SecurityContext is already installed",
                SecurityContextReason.ALREADY_ACTIVE,
            )

    context.validate(require_active=False)
    context._lease.activate()
    token = _ACTIVE_CONTEXT.set(context)
    try:
        yield context
    finally:
        context._lease.close()
        _ACTIVE_CONTEXT.reset(token)


ToolHandler = Callable[..., ToolResult]
_TOOL_HANDLERS: dict[str, ToolHandler] = {}


def _register_tool(name: str, handler: ToolHandler) -> None:
    """Register one private implementation for a supported product tool."""

    if name not in SUPPORTED_TOOL_NAMES:
        raise ValueError(f"Unsupported product tool registration: {name}")
    _TOOL_HANDLERS[name] = handler


def _correlation_metadata(
    context: SecurityContext,
    action_id: str,
    decision: str,
    authorization: ScopeDecision | None = None,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "request_id": context.request_id,
        "action_id": action_id,
        "decision": decision,
        "policy_version": context.policy_version,
    }
    if authorization is not None:
        metadata["authorization"] = authorization.to_metadata()
    if context.session_id is not None:
        metadata["session_id"] = context.session_id
    return metadata


def _with_correlation(
    result: ToolResult,
    context: SecurityContext,
    action_id: str,
    decision: str,
    authorization: ScopeDecision | None = None,
) -> ToolResult:
    return ToolResult(
        success=result.success,
        output=result.output,
        error=result.error,
        metadata={
            **result.metadata,
            **_correlation_metadata(
                context,
                action_id,
                decision,
                authorization,
            ),
        },
    )


def _decision_for_result(result: ToolResult) -> str:
    if result.success:
        return "allow"
    metadata = result.metadata
    if (
        "rejection_reason" in metadata
        or "policy_decision" in metadata
        or metadata.get("confirmation") in {"denied", "refused"}
    ):
        return "deny"
    return "allow"


def _audit(
    context: SecurityContext,
    *,
    phase: str,
    tool: str,
    args: dict[str, Any],
    action_id: str,
    decision: str | None,
    result: ToolResult | None = None,
    attempt_event_id: str | None = None,
    authorization: ScopeDecision | None = None,
) -> AuditRecord | None:
    logger = context.audit_logger
    if logger is None:
        return None
    return logger.record(
        tool,
        args,
        success=None if result is None else result.success,
        error=None if result is None else result.error,
        metadata=(
            {"authorization": authorization.to_metadata()}
            if result is None and authorization is not None
            else {}
            if result is None
            else result.metadata
        ),
        session_id=context.session_id,
        phase=phase,
        request_id=context.request_id,
        action_id=action_id,
        decision=decision,
        attempt_event_id=attempt_event_id,
    )


def _result_evidence(
    context: SecurityContext,
    *,
    tool: str,
    args: dict[str, Any],
    action_id: str,
    result: ToolResult,
    attempt: AuditRecord | None,
    authorization: ScopeDecision,
) -> AuditRecord | None:
    completed = _audit(
        context,
        phase="result",
        tool=tool,
        args=args,
        action_id=action_id,
        decision=result.metadata["decision"],
        result=result,
        attempt_event_id=None if attempt is None else attempt.event_id,
        authorization=authorization,
    )
    if context.session is not None:
        context.session.append_tool_call(
            tool,
            args,
            success=result.success,
            metadata=result.metadata,
            output=result.output,
            error=result.error,
            request_id=context.request_id,
            action_id=action_id,
            audit_attempt_event_id=None if attempt is None else attempt.event_id,
            audit_result_event_id=(
                None if completed is None else completed.event_id
            ),
        )
    return completed


def _finalize_evidence(
    context: SecurityContext,
    *,
    tool: str,
    args: dict[str, Any],
    action_id: str,
    result: ToolResult,
    attempt: AuditRecord | None,
    authorization: ScopeDecision,
) -> ToolResult:
    try:
        _result_evidence(
            context,
            tool=tool,
            args=args,
            action_id=action_id,
            result=result,
            attempt=attempt,
            authorization=authorization,
        )
    except Exception:
        return _with_correlation(
            _err(
                "Durable result evidence could not be persisted",
                rejection_reason="audit_failure",
            ),
            context,
            action_id,
            "deny",
            authorization,
        )
    return result


def _context_refusal(error: SecurityContextError) -> ToolResult:
    return _err(str(error), rejection_reason=error.reason.value, decision="deny")


def _authorization_for_action(
    context: SecurityContext,
    tool_name: str,
    tool_args: dict[str, Any],
) -> ScopeDecision:
    """Resolve and evaluate current authority without running a tool handler."""

    required = (
        required_scopes_for_action(tool_name, tool_args)
        if tool_name in SUPPORTED_TOOL_NAMES
        else frozenset()
    )
    try:
        current: object = (
            context.principal_resolver()
            if context.principal_resolver is not None
            else context.principal
        )
    except Exception:
        current = object()
    return evaluate_principal_scopes(context.principal, current, required)


def _authorization_refusal(
    authorization: ScopeDecision,
) -> ToolResult:
    reason = authorization.reason
    if reason is AuthorizationReason.SCOPE_INSUFFICIENT:
        message = "Council principal lacks one or more required scopes"
    elif reason is AuthorizationReason.PRINCIPAL_REVOKED:
        message = "Council principal authority is no longer current"
    else:
        message = "Council principal authorization is missing or invalid"
    return _err(
        message,
        rejection_reason=reason.value,
    )


def invoke(tool_name: str, **tool_args: Any) -> ToolResult:
    """Invoke one product tool through the mandatory policy middleware."""

    action_id = str(uuid.uuid4())
    try:
        context = require_security_context()
    except SecurityContextError as exc:
        return _context_refusal(exc)

    authorization = _authorization_for_action(context, tool_name, tool_args)
    try:
        attempt = _audit(
            context,
            phase="attempt",
            tool=tool_name,
            args=tool_args,
            action_id=action_id,
            decision=None,
            authorization=authorization,
        )
    except Exception:
        return _with_correlation(
            _err(
                "Durable attempt evidence could not be persisted",
                rejection_reason="audit_failure",
            ),
            context,
            action_id,
            "deny",
            authorization,
        )

    if not authorization.allowed:
        result = _with_correlation(
            _authorization_refusal(authorization),
            context,
            action_id,
            "deny",
            authorization,
        )
        return _finalize_evidence(
            context,
            tool=tool_name,
            args=tool_args,
            action_id=action_id,
            result=result,
            attempt=attempt,
            authorization=authorization,
        )

    handler = _TOOL_HANDLERS.get(tool_name)
    if handler is None:
        result = _with_correlation(
            _err(
                f"Unknown product tool: {tool_name}",
                rejection_reason="unknown_tool",
            ),
            context,
            action_id,
            "deny",
            authorization,
        )
        return _finalize_evidence(
            context,
            tool=tool_name,
            args=tool_args,
            action_id=action_id,
            result=result,
            attempt=attempt,
            authorization=authorization,
        )

    if len(context.tracker.summaries) >= context.tracker.max_tool_calls:
        context.tracker.limit_reached = True
        result = _with_correlation(
            _err(
                f"Tool call limit reached ({context.tracker.max_tool_calls}). "
                "No further tool calls are allowed in this run.",
                rejection_reason="tool_limit",
                max_tool_calls=context.tracker.max_tool_calls,
            ),
            context,
            action_id,
            "deny",
            authorization,
        )
        return _finalize_evidence(
            context,
            tool=tool_name,
            args=tool_args,
            action_id=action_id,
            result=result,
            attempt=attempt,
            authorization=authorization,
        )

    try:
        raw_result = handler(context, **tool_args)
        if not isinstance(raw_result, ToolResult):
            raise TypeError("tool handler must return ToolResult")
    except Exception as exc:
        raw_result = _err(
            f"Tool handler failed: {exc}",
            rejection_reason="tool_exception",
        )

    decision = _decision_for_result(raw_result)
    result = _with_correlation(
        raw_result,
        context,
        action_id,
        decision,
        authorization,
    )
    summary = context.tracker.record_result(tool_name, tool_args, result)
    if summary is None:
        result = _with_correlation(
            _err(
                "Tool result could not be tracked",
                rejection_reason="tracker_failure",
            ),
            context,
            action_id,
            "deny",
            authorization,
        )

    return _finalize_evidence(
        context,
        tool=tool_name,
        args=tool_args,
        action_id=action_id,
        result=result,
        attempt=attempt,
        authorization=authorization,
    )
