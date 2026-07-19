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


@dataclass(frozen=True)
class ConfirmationPolicy:
    mode: ConfirmMode = ConfirmMode.COMPAT
    confirm_fn: ConfirmFn | None = None


@dataclass(frozen=True)
class ConfirmationResult:
    allowed: bool
    outcome: ConfirmationOutcome


_POLICY: ContextVar[ConfirmationPolicy] = ContextVar(
    "council_confirmation_policy",
    default=ConfirmationPolicy(),
)


def get_confirmation_policy() -> ConfirmationPolicy:
    return _POLICY.get()


def set_confirmation_policy(policy: ConfirmationPolicy) -> Token[ConfirmationPolicy]:
    return _POLICY.set(policy)


def reset_confirmation_policy(token: Token[ConfirmationPolicy]) -> None:
    _POLICY.reset(token)


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
    }


def require_confirmation(kind: ActionKind, detail: str) -> ConfirmationResult:
    """Decide whether a gated action may proceed under the active policy."""
    policy = get_confirmation_policy()
    mode = policy.mode

    if not _needs_confirmation(kind, mode):
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
