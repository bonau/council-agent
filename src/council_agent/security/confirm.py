"""Interactive confirmation gate for mutating / dangerous tool actions (v0.7)."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Iterator

from rich.prompt import Confirm

ConfirmFn = Callable[[str], bool]


class ConfirmMode(str, Enum):
    ASK = "ask"
    AUTO = "auto"
    REFUSE = "refuse"
    COMPAT = "compat"


class ConfirmationOutcome(str, Enum):
    APPROVED = "approved"
    DENIED = "denied"
    AUTO = "auto"
    REFUSED = "refused"
    COMPAT_ALLOW = "compat_allow"


class ActionKind(str, Enum):
    """Kinds of actions that may require confirmation."""

    DANGEROUS_SHELL = "dangerous_shell"
    WRITE_SHELL = "write_shell"
    WRITE_FILE = "write_file"
    DELETE_FILE = "delete_file"
    READ_FILE = "read_file"
    READ_SHELL = "read_shell"
    RUN_TESTS = "run_tests"


@dataclass(frozen=True)
class ConfirmationPolicy:
    mode: ConfirmMode = ConfirmMode.COMPAT
    confirm_fn: ConfirmFn | None = None


@dataclass(frozen=True)
class ConfirmationResult:
    allowed: bool
    outcome: ConfirmationOutcome


@dataclass(frozen=True)
class _ConfirmationPolicyToken:
    legacy: Token[ConfirmationPolicy]
    context: object | None


_POLICY: ContextVar[ConfirmationPolicy] = ContextVar(
    "council_confirmation_policy",
    default=ConfirmationPolicy(),
)


def get_confirmation_policy() -> ConfirmationPolicy:
    from council_agent.security.middleware import get_security_context

    context = get_security_context()
    if context is not None:
        try:
            context.validate(require_active=True)
        except RuntimeError:
            pass
        else:
            return context.confirmation
    return _POLICY.get()


def set_confirmation_policy(policy: ConfirmationPolicy) -> _ConfirmationPolicyToken:
    from council_agent.security.middleware import _set_security_context_view

    legacy_token = _POLICY.set(policy)
    try:
        context_token = _set_security_context_view(confirmation=policy)
    except Exception:
        _POLICY.reset(legacy_token)
        raise
    return _ConfirmationPolicyToken(legacy=legacy_token, context=context_token)


def reset_confirmation_policy(token: _ConfirmationPolicyToken) -> None:
    from council_agent.security.middleware import _reset_security_context_view

    _reset_security_context_view(token.context)
    _POLICY.reset(token.legacy)


@contextmanager
def confirmation_policy(
    mode: ConfirmMode,
    confirm_fn: ConfirmFn | None = None,
) -> Iterator[ConfirmationPolicy]:
    """Install a confirmation policy for the duration of the context."""
    policy = ConfirmationPolicy(mode=mode, confirm_fn=confirm_fn)
    token = set_confirmation_policy(policy)
    try:
        yield policy
    finally:
        reset_confirmation_policy(token)


def resolve_cli_confirm_mode(*, yes: bool, is_tty: bool) -> ConfirmMode:
    """Map CLI flags / TTY state to a product confirmation mode."""
    if yes:
        return ConfirmMode.AUTO
    if is_tty:
        return ConfirmMode.ASK
    return ConfirmMode.REFUSE


def default_confirm_fn(message: str) -> bool:
    """Rich TUI confirmation; default No (Enter declines)."""
    return Confirm.ask(message, default=False)


def _needs_confirmation(kind: ActionKind, mode: ConfirmMode) -> bool:
    if mode is ConfirmMode.COMPAT:
        return kind is ActionKind.DANGEROUS_SHELL
    return kind in {
        ActionKind.DANGEROUS_SHELL,
        ActionKind.WRITE_SHELL,
        ActionKind.WRITE_FILE,
        ActionKind.DELETE_FILE,
        ActionKind.RUN_TESTS,
    }


def require_confirmation(kind: ActionKind, detail: str) -> ConfirmationResult:
    """Decide whether a gated action may proceed under the active policy."""
    return evaluate_confirmation(get_confirmation_policy(), kind, detail)


def evaluate_confirmation(
    policy: ConfirmationPolicy,
    kind: ActionKind,
    detail: str,
    *,
    force: bool = False,
    auto_approve: bool = False,
) -> ConfirmationResult:
    """Evaluate one action against an explicit confirmation-policy snapshot."""

    if auto_approve:
        return ConfirmationResult(allowed=True, outcome=ConfirmationOutcome.AUTO)

    mode = policy.mode

    if not force and not _needs_confirmation(kind, mode):
        return ConfirmationResult(allowed=True, outcome=ConfirmationOutcome.COMPAT_ALLOW)

    if mode is ConfirmMode.AUTO:
        return ConfirmationResult(allowed=True, outcome=ConfirmationOutcome.AUTO)

    if mode is ConfirmMode.REFUSE or mode is ConfirmMode.COMPAT:
        return ConfirmationResult(allowed=False, outcome=ConfirmationOutcome.REFUSED)

    # ask
    confirm_fn = policy.confirm_fn or default_confirm_fn
    message = f"Allow {kind.value}: {detail}?"
    if confirm_fn(message):
        return ConfirmationResult(allowed=True, outcome=ConfirmationOutcome.APPROVED)
    return ConfirmationResult(allowed=False, outcome=ConfirmationOutcome.DENIED)


def evaluate_tier_aware_confirmation(
    policy: ConfirmationPolicy,
    kind: ActionKind,
    detail: str,
) -> ConfirmationResult:
    """Apply active Trust Tier translation on top of ConfirmMode."""

    from council_agent.security.trust import get_active_tier_translation

    translation = get_active_tier_translation()
    if translation is None:
        return evaluate_confirmation(policy, kind, detail)
    if translation.auto_approve_interaction:
        return evaluate_confirmation(
            policy,
            kind,
            detail,
            auto_approve=True,
        )
    if translation.require_confirmation:
        return evaluate_confirmation(
            policy,
            kind,
            detail,
            force=True,
        )
    return evaluate_confirmation(policy, kind, detail)
