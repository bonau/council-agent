"""Mandatory policy middleware and request-scoped security context."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Iterator

from council_agent.sandbox.session import SessionManager
from council_agent.sandbox.workspace import WorkspaceGuard
from council_agent.security.audit import AuditLogger
from council_agent.security.confirm import ConfirmationPolicy
from council_agent.security.policy import CouncilPolicy, effective_denied_paths
from council_agent.tools.base import ToolResult, _err
from council_agent.tools.tracker import ToolCallTracker

POLICY_VERSION_UNVERSIONED = "v0.9-unversioned"
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
    session_id: str | None = None
    session: SessionManager | None = None
    audit_logger: AuditLogger | None = None
    policy_version: str = POLICY_VERSION_UNVERSIONED
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
        session: SessionManager | None = None,
        audit_logger: AuditLogger | None = None,
        policy_version: str = POLICY_VERSION_UNVERSIONED,
    ) -> SecurityContext:
        """Build and validate one context snapshot for a product scope."""

        resolved_session_id = session_id
        if resolved_session_id is None and session is not None:
            resolved_session_id = session.meta.session_id
        if resolved_session_id is None and audit_logger is not None:
            resolved_session_id = audit_logger.session_id

        context = cls(
            request_id=request_id or str(uuid.uuid4()),
            workspace=WorkspaceGuard(
                Path(workspace_root),
                denied_patterns=effective_denied_paths(policy),
            ),
            policy=policy,
            confirmation=confirmation or ConfirmationPolicy(),
            tracker=tracker if tracker is not None else ToolCallTracker(),
            session_id=resolved_session_id,
            session=session,
            audit_logger=audit_logger,
            policy_version=policy_version,
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
        if not isinstance(self.tracker, ToolCallTracker):
            raise SecurityContextError(
                "Security context tracker is invalid",
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
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "request_id": context.request_id,
        "action_id": action_id,
        "decision": decision,
        "policy_version": context.policy_version,
    }
    if context.session_id is not None:
        metadata["session_id"] = context.session_id
    return metadata


def _with_correlation(
    result: ToolResult,
    context: SecurityContext,
    action_id: str,
    decision: str,
) -> ToolResult:
    return ToolResult(
        success=result.success,
        output=result.output,
        error=result.error,
        metadata={
            **result.metadata,
            **_correlation_metadata(context, action_id, decision),
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
) -> None:
    logger = context.audit_logger
    if logger is None:
        return
    logger.record(
        tool,
        args,
        success=None if result is None else result.success,
        error=None if result is None else result.error,
        metadata={} if result is None else result.metadata,
        session_id=context.session_id,
        phase=phase,
        request_id=context.request_id,
        action_id=action_id,
        decision=decision,
    )


def _context_refusal(error: SecurityContextError) -> ToolResult:
    return _err(str(error), rejection_reason=error.reason.value, decision="deny")


def invoke(tool_name: str, **tool_args: Any) -> ToolResult:
    """Invoke one product tool through the mandatory policy middleware."""

    action_id = str(uuid.uuid4())
    try:
        context = require_security_context()
    except SecurityContextError as exc:
        return _context_refusal(exc)

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
        )
        _audit(
            context,
            phase="attempt",
            tool=tool_name,
            args=tool_args,
            action_id=action_id,
            decision=None,
        )
        _audit(
            context,
            phase="result",
            tool=tool_name,
            args=tool_args,
            action_id=action_id,
            decision="deny",
            result=result,
        )
        return result

    try:
        _audit(
            context,
            phase="attempt",
            tool=tool_name,
            args=tool_args,
            action_id=action_id,
            decision=None,
        )
    except Exception as exc:
        return _with_correlation(
            _err(
                f"Audit attempt failed: {exc}",
                rejection_reason="audit_failure",
            ),
            context,
            action_id,
            "deny",
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
        )
        _audit(
            context,
            phase="result",
            tool=tool_name,
            args=tool_args,
            action_id=action_id,
            decision="deny",
            result=result,
        )
        return result

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
    result = _with_correlation(raw_result, context, action_id, decision)
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
        )

    if context.session is not None:
        context.session.append_tool_call(
            tool_name,
            tool_args,
            success=result.success,
            metadata=result.metadata,
            output=result.output,
            error=result.error,
        )

    _audit(
        context,
        phase="result",
        tool=tool_name,
        args=tool_args,
        action_id=action_id,
        decision=result.metadata["decision"],
        result=result,
    )
    return result
