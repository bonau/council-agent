"""Project policy file loading and evaluation (v0.9)."""

from __future__ import annotations

import fnmatch
from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Iterator

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from council_agent.sandbox.workspace import DEFAULT_DENIED_PATTERNS

POLICY_FILENAME = "council.policy.yaml"


class PolicyError(Exception):
    """Base error for policy loading or evaluation."""


class PolicyValidationError(PolicyError):
    """Raised when ``council.policy.yaml`` fails schema or YAML validation."""


class PolicyCommandReason(str, Enum):
    DENIED = "denied"
    NOT_ALLOWED = "not_allowed"


@dataclass(frozen=True)
class PolicyCommandDecision:
    """Result of evaluating a shell command against the active policy."""

    allowed: bool
    reason: PolicyCommandReason | None = None
    matched_pattern: str | None = None


class CouncilPolicy(BaseModel):
    """Validated subset of ``council.policy.yaml`` fields for v0.9."""

    model_config = ConfigDict(extra="ignore")

    allowed_commands: list[str] = Field(default_factory=list)
    denied_commands: list[str] = Field(default_factory=list)
    denied_paths: list[str] = Field(default_factory=list)


@dataclass(frozen=True)
class _ActivePolicyToken:
    legacy: Token[CouncilPolicy | None]
    context: object | None


_ACTIVE_POLICY: ContextVar[CouncilPolicy | None] = ContextVar(
    "council_active_policy",
    default=None,
)


def policy_path(project_root: Path | str) -> Path:
    return Path(project_root) / POLICY_FILENAME


def load_policy_file(project_root: Path | str) -> CouncilPolicy | None:
    """Load and validate ``council.policy.yaml``.

    Returns ``None`` when the file is missing. Raises
    :class:`PolicyValidationError` when the file exists but is invalid.
    """
    path = policy_path(project_root)
    if not path.is_file():
        return None

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise PolicyValidationError(
            f"Invalid YAML in policy file {path}: {exc}"
        ) from exc

    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise PolicyValidationError(
            f"Policy file {path} must contain a mapping at the top level"
        )

    try:
        return CouncilPolicy.model_validate(raw)
    except ValidationError as exc:
        raise PolicyValidationError(
            f"Invalid policy schema in {path}: {exc}"
        ) from exc


def get_active_policy() -> CouncilPolicy | None:
    from council_agent.security.middleware import get_security_context

    context = get_security_context()
    if context is not None:
        try:
            context.validate(require_active=True)
        except RuntimeError:
            pass
        else:
            return context.policy
    return _ACTIVE_POLICY.get()


def set_active_policy(policy: CouncilPolicy | None) -> _ActivePolicyToken:
    from council_agent.security.middleware import _set_security_context_view

    legacy_token = _ACTIVE_POLICY.set(policy)
    try:
        context_token = _set_security_context_view(policy=policy)
    except Exception:
        _ACTIVE_POLICY.reset(legacy_token)
        raise
    return _ActivePolicyToken(legacy=legacy_token, context=context_token)


def reset_active_policy(token: _ActivePolicyToken) -> None:
    from council_agent.security.middleware import _reset_security_context_view

    _reset_security_context_view(token.context)
    _ACTIVE_POLICY.reset(token.legacy)


@contextmanager
def active_policy(policy: CouncilPolicy | None) -> Iterator[CouncilPolicy | None]:
    """Install a policy for the duration of the context."""
    token = set_active_policy(policy)
    try:
        yield policy
    finally:
        reset_active_policy(token)


def _pattern_matches(command: str, pattern: str) -> bool:
    return fnmatch.fnmatch(command.lower(), pattern.lower())


def evaluate_command(
    command: str,
    policy: CouncilPolicy | None = None,
) -> PolicyCommandDecision:
    """Evaluate a command against a policy (or the active policy when omitted)."""
    effective = policy if policy is not None else get_active_policy()
    if effective is None:
        return PolicyCommandDecision(allowed=True)

    for pattern in effective.denied_commands:
        if _pattern_matches(command, pattern):
            return PolicyCommandDecision(
                allowed=False,
                reason=PolicyCommandReason.DENIED,
                matched_pattern=pattern,
            )

    if effective.allowed_commands:
        for pattern in effective.allowed_commands:
            if _pattern_matches(command, pattern):
                return PolicyCommandDecision(allowed=True)
        return PolicyCommandDecision(
            allowed=False,
            reason=PolicyCommandReason.NOT_ALLOWED,
            matched_pattern=None,
        )

    return PolicyCommandDecision(allowed=True)


def evaluate_command_policy(command: str) -> PolicyCommandDecision:
    """Evaluate ``command`` against the currently active policy."""
    return evaluate_command(command, policy=None)


def effective_denied_paths(
    policy: CouncilPolicy | None = None,
) -> tuple[str, ...]:
    """Return default denylist ∪ policy ``denied_paths`` (order-preserving)."""
    effective = policy if policy is not None else get_active_policy()
    merged: list[str] = []
    seen: set[str] = set()
    for pattern in list(DEFAULT_DENIED_PATTERNS) + list(
        effective.denied_paths if effective is not None else ()
    ):
        if pattern in seen:
            continue
        seen.add(pattern)
        merged.append(pattern)
    return tuple(merged)
