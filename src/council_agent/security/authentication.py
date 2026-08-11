"""Process-local, replay-resistant session step-up authentication."""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, TypeAlias

from pydantic import SecretStr

from council_agent.security.audit import AuditLogger
from council_agent.security.principal import Principal

DEFAULT_CHALLENGE_TTL = timedelta(seconds=60)
DEFAULT_TOKEN_TTL = timedelta(minutes=5)
DEFAULT_FRESHNESS = timedelta(seconds=60)
AUTHENTICATION_PURPOSE_HIGH_RISK = "high-risk-action"
REFERENCE_PREFIX = "sha256:"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


Clock: TypeAlias = Callable[[], datetime]


def masked_reference(value: str | bytes) -> str:
    """Return a stable, non-reversible reference for runtime evidence."""

    encoded = value.encode("utf-8") if isinstance(value, str) else value
    return f"{REFERENCE_PREFIX}{hashlib.sha256(encoded).hexdigest()[:32]}"


def _canonical_action(tool_name: str, tool_args: Mapping[str, Any]) -> str:
    return json.dumps(
        {"tool": tool_name, "args": tool_args},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=lambda value: {
            "type": f"{type(value).__module__}.{type(value).__qualname__}"
        },
        allow_nan=False,
    )


def _require_utc(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")


@dataclass(frozen=True)
class AuthenticationBinding:
    """Exact runtime authority to which challenge and token state is bound."""

    principal_ref: str
    workspace_ref: str
    session_id: str
    purpose: str
    action_ref: str

    def __post_init__(self) -> None:
        for field_name in (
            "principal_ref",
            "workspace_ref",
            "session_id",
            "purpose",
            "action_ref",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"Authentication binding {field_name} must be non-empty")

    @classmethod
    def for_action(
        cls,
        principal: Principal,
        workspace_root: Path | str,
        session_id: str,
        tool_name: str,
        tool_args: Mapping[str, Any],
        *,
        purpose: str = AUTHENTICATION_PURPOSE_HIGH_RISK,
    ) -> AuthenticationBinding:
        """Build one binding without retaining raw workspace or action values."""

        principal.__post_init__()
        workspace = str(Path(workspace_root).expanduser().resolve())
        return cls(
            principal_ref=principal.audit_ref,
            workspace_ref=masked_reference(workspace),
            session_id=session_id,
            purpose=purpose,
            action_ref=masked_reference(_canonical_action(tool_name, tool_args)),
        )

    def to_metadata(self) -> dict[str, str]:
        return {
            "principal_ref": self.principal_ref,
            "workspace_ref": self.workspace_ref,
            "session_id": self.session_id,
            "purpose": self.purpose,
            "action_ref": self.action_ref,
        }


@dataclass(frozen=True, repr=False)
class AuthenticationChallenge:
    """Opaque one-use challenge. Its representation never reveals raw values."""

    challenge_id: SecretStr
    nonce: SecretStr
    binding: AuthenticationBinding
    issued_at: datetime
    expires_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.challenge_id, SecretStr) or not self.challenge_id.get_secret_value():
            raise ValueError("Authentication challenge id must be secret and non-empty")
        if not isinstance(self.nonce, SecretStr) or not self.nonce.get_secret_value():
            raise ValueError("Authentication challenge nonce must be secret and non-empty")
        _require_utc(self.issued_at, "issued_at")
        _require_utc(self.expires_at, "expires_at")
        if self.expires_at <= self.issued_at:
            raise ValueError("Authentication challenge expiry must follow issue time")

    @property
    def audit_ref(self) -> str:
        return masked_reference(self.challenge_id.get_secret_value())

    def __repr__(self) -> str:
        return (
            "AuthenticationChallenge("
            f"challenge_ref={self.audit_ref!r}, binding={self.binding!r}, "
            f"issued_at={self.issued_at!r}, expires_at={self.expires_at!r})"
        )


@dataclass(frozen=True, repr=False)
class StepUpToken:
    """Opaque one-use proof returned only after challenge authentication."""

    value: SecretStr

    def __post_init__(self) -> None:
        if not isinstance(self.value, SecretStr) or not self.value.get_secret_value():
            raise ValueError("Step-up token must be secret and non-empty")

    @property
    def audit_ref(self) -> str:
        return masked_reference(self.value.get_secret_value())

    def __repr__(self) -> str:
        return f"StepUpToken(token_ref={self.audit_ref!r})"


class AuthenticationReason(str, Enum):
    """Stable reasons for challenge and step-up decisions."""

    NOT_REQUIRED = "authentication_not_required"
    CHALLENGE_ISSUED = "authentication_challenge_issued"
    AUTHENTICATED = "authentication_succeeded"
    STEP_UP_ALLOWED = "step_up_allowed"
    MISSING = "authentication_missing"
    INVALID = "authentication_invalid"
    FAILED = "authentication_failed"
    EXPIRED = "authentication_expired"
    REVOKED = "authentication_revoked"
    REPLAY = "authentication_replay"
    BINDING_MISMATCH = "authentication_binding_mismatch"
    PROVIDER_ERROR = "authentication_provider_error"


@dataclass(frozen=True)
class AuthenticationDecision:
    """Normalized result safe to attach to tool and lifecycle evidence."""

    allowed: bool
    reason: AuthenticationReason
    required: bool
    binding: AuthenticationBinding | None = None
    challenge_ref: str | None = None
    token_ref: str | None = None

    def to_metadata(self) -> dict[str, Any]:
        return {
            "authentication_decision": "allow" if self.allowed else "deny",
            "reason": self.reason.value,
            "required": self.required,
            "binding": None if self.binding is None else self.binding.to_metadata(),
            "challenge_ref": self.challenge_ref,
            "token_ref": self.token_ref,
        }


@dataclass(frozen=True)
class ChallengeIssue:
    challenge: AuthenticationChallenge | None
    decision: AuthenticationDecision


@dataclass(frozen=True)
class ChallengeCompletion:
    token: StepUpToken | None
    decision: AuthenticationDecision


class AuthenticationEventType(str, Enum):
    SUCCESS = "authentication_success"
    FAILURE = "authentication_failure"
    EXPIRY = "authentication_expiry"
    REVOCATION = "authentication_revocation"
    REPLAY = "authentication_replay"


@dataclass(frozen=True)
class AuthenticationEvent:
    """One credential-free lifecycle event for an optional audit sink."""

    event_type: AuthenticationEventType
    decision: AuthenticationDecision
    timestamp: datetime

    def to_metadata(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type.value,
            **self.decision.to_metadata(),
            "timestamp": self.timestamp.isoformat(),
        }


AuthenticationEventSink: TypeAlias = Callable[[AuthenticationEvent], None]
StepUpProvider: TypeAlias = Callable[[AuthenticationBinding], StepUpToken | None]


def authentication_audit_sink(
    logger: AuditLogger | None,
    *,
    request_id: str,
    session_id: str,
) -> AuthenticationEventSink | None:
    """Adapt credential-free lifecycle events to administrative audit records."""

    if logger is None:
        return None
    if not request_id.strip() or not session_id.strip():
        raise ValueError("Authentication audit correlation must be non-empty")

    def _record(event: AuthenticationEvent) -> None:
        metadata = event.to_metadata()
        logger.record(
            "session_auth",
            {
                "event_type": event.event_type.value,
                "challenge_ref": event.decision.challenge_ref,
                "token_ref": event.decision.token_ref,
            },
            success=event.decision.allowed,
            error=None if event.decision.allowed else event.decision.reason.value,
            metadata={"session_authentication": metadata},
            session_id=session_id,
            timestamp=event.timestamp.isoformat(),
            request_id=request_id,
            decision="allow" if event.decision.allowed else "deny",
        )

    return _record


@dataclass(frozen=True)
class _ChallengeState:
    binding: AuthenticationBinding
    envelope: bytes
    issued_at: datetime
    expires_at: datetime


@dataclass(frozen=True)
class _TokenState:
    binding: AuthenticationBinding
    issued_at: datetime
    expires_at: datetime


class AuthenticationManager:
    """Own one process-local verifier, challenges, tokens, and replay tombstones."""

    def __init__(
        self,
        verifier: SecretStr,
        *,
        clock: Clock = _utc_now,
        challenge_ttl: timedelta = DEFAULT_CHALLENGE_TTL,
        token_ttl: timedelta = DEFAULT_TOKEN_TTL,
        event_sink: AuthenticationEventSink | None = None,
    ) -> None:
        if not isinstance(verifier, SecretStr):
            raise TypeError("Authentication verifier must be a SecretStr")
        secret = verifier.get_secret_value()
        if not secret:
            raise ValueError("Authentication verifier must be non-empty")
        if challenge_ttl <= timedelta(0) or token_ttl <= timedelta(0):
            raise ValueError("Authentication lifetimes must be positive")
        self._verifier_key = hashlib.sha256(secret.encode("utf-8")).digest()
        self._clock = clock
        self._challenge_ttl = challenge_ttl
        self._token_ttl = token_ttl
        self._event_sink = event_sink
        self._challenges: dict[str, _ChallengeState] = {}
        self._challenge_tombstones: set[str] = set()
        self._tokens: dict[str, _TokenState] = {}
        self._token_tombstones: set[str] = set()
        self._revoked = False

    @property
    def revoked(self) -> bool:
        return self._revoked

    def issue_challenge(
        self,
        binding: AuthenticationBinding,
    ) -> ChallengeIssue:
        now = self._now()
        if self._revoked:
            decision = self._decision(
                False,
                AuthenticationReason.REVOKED,
                binding=binding,
            )
            self._emit(AuthenticationEventType.REVOCATION, decision, now)
            return ChallengeIssue(None, decision)

        challenge = AuthenticationChallenge(
            challenge_id=SecretStr(secrets.token_urlsafe(32)),
            nonce=SecretStr(secrets.token_urlsafe(32)),
            binding=binding,
            issued_at=now,
            expires_at=now + self._challenge_ttl,
        )
        envelope = _challenge_envelope(challenge)
        self._challenges[challenge.audit_ref] = _ChallengeState(
            binding=binding,
            envelope=envelope,
            issued_at=challenge.issued_at,
            expires_at=challenge.expires_at,
        )
        return ChallengeIssue(
            challenge,
            self._decision(
                True,
                AuthenticationReason.CHALLENGE_ISSUED,
                binding=binding,
                challenge_ref=challenge.audit_ref,
            ),
        )

    def complete_challenge(
        self,
        challenge: AuthenticationChallenge,
        response: SecretStr,
    ) -> ChallengeCompletion:
        now = self._now()
        if not isinstance(challenge, AuthenticationChallenge) or not isinstance(
            response, SecretStr
        ):
            decision = self._decision(False, AuthenticationReason.INVALID)
            self._emit(AuthenticationEventType.FAILURE, decision, now)
            return ChallengeCompletion(None, decision)

        challenge_ref = challenge.audit_ref
        if self._revoked:
            decision = self._decision(
                False,
                AuthenticationReason.REVOKED,
                binding=challenge.binding,
                challenge_ref=challenge_ref,
            )
            self._emit(AuthenticationEventType.REVOCATION, decision, now)
            return ChallengeCompletion(None, decision)
        if challenge_ref in self._challenge_tombstones:
            decision = self._decision(
                False,
                AuthenticationReason.REPLAY,
                binding=challenge.binding,
                challenge_ref=challenge_ref,
            )
            self._emit(AuthenticationEventType.REPLAY, decision, now)
            return ChallengeCompletion(None, decision)

        state = self._challenges.pop(challenge_ref, None)
        self._challenge_tombstones.add(challenge_ref)
        if state is None:
            decision = self._decision(
                False,
                AuthenticationReason.INVALID,
                binding=challenge.binding,
                challenge_ref=challenge_ref,
            )
            self._emit(AuthenticationEventType.FAILURE, decision, now)
            return ChallengeCompletion(None, decision)
        if now < state.issued_at or now >= state.expires_at:
            decision = self._decision(
                False,
                AuthenticationReason.EXPIRED,
                binding=state.binding,
                challenge_ref=challenge_ref,
            )
            self._emit(AuthenticationEventType.EXPIRY, decision, now)
            return ChallengeCompletion(None, decision)
        if (
            challenge.binding != state.binding
            or not hmac.compare_digest(_challenge_envelope(challenge), state.envelope)
        ):
            decision = self._decision(
                False,
                AuthenticationReason.BINDING_MISMATCH,
                binding=challenge.binding,
                challenge_ref=challenge_ref,
            )
            self._emit(AuthenticationEventType.FAILURE, decision, now)
            return ChallengeCompletion(None, decision)

        expected = hmac.digest(self._verifier_key, state.envelope, "sha256").hex()
        if not hmac.compare_digest(response.get_secret_value(), expected):
            decision = self._decision(
                False,
                AuthenticationReason.FAILED,
                binding=state.binding,
                challenge_ref=challenge_ref,
            )
            self._emit(AuthenticationEventType.FAILURE, decision, now)
            return ChallengeCompletion(None, decision)

        token = StepUpToken(SecretStr(secrets.token_urlsafe(48)))
        self._tokens[token.audit_ref] = _TokenState(
            binding=state.binding,
            issued_at=now,
            expires_at=now + self._token_ttl,
        )
        decision = self._decision(
            True,
            AuthenticationReason.AUTHENTICATED,
            binding=state.binding,
            challenge_ref=challenge_ref,
            token_ref=token.audit_ref,
        )
        self._emit(AuthenticationEventType.SUCCESS, decision, now)
        return ChallengeCompletion(token, decision)

    def consume_step_up(
        self,
        token: StepUpToken,
        binding: AuthenticationBinding,
        *,
        freshness: timedelta = DEFAULT_FRESHNESS,
    ) -> AuthenticationDecision:
        now = self._now()
        if freshness <= timedelta(0):
            raise ValueError("Authentication freshness must be positive")
        if not isinstance(token, StepUpToken):
            decision = self._decision(
                False,
                AuthenticationReason.INVALID,
                binding=binding,
            )
            self._emit(AuthenticationEventType.FAILURE, decision, now)
            return decision

        token_ref = token.audit_ref
        if self._revoked:
            decision = self._decision(
                False,
                AuthenticationReason.REVOKED,
                binding=binding,
                token_ref=token_ref,
            )
            self._emit(AuthenticationEventType.REVOCATION, decision, now)
            return decision
        if token_ref in self._token_tombstones:
            decision = self._decision(
                False,
                AuthenticationReason.REPLAY,
                binding=binding,
                token_ref=token_ref,
            )
            self._emit(AuthenticationEventType.REPLAY, decision, now)
            return decision

        state = self._tokens.pop(token_ref, None)
        self._token_tombstones.add(token_ref)
        if state is None:
            decision = self._decision(
                False,
                AuthenticationReason.INVALID,
                binding=binding,
                token_ref=token_ref,
            )
            self._emit(AuthenticationEventType.FAILURE, decision, now)
            return decision

        age = now - state.issued_at
        if (
            now < state.issued_at
            or now >= state.expires_at
            or age > freshness
        ):
            decision = self._decision(
                False,
                AuthenticationReason.EXPIRED,
                binding=state.binding,
                token_ref=token_ref,
            )
            self._emit(AuthenticationEventType.EXPIRY, decision, now)
            return decision
        if binding != state.binding:
            decision = self._decision(
                False,
                AuthenticationReason.BINDING_MISMATCH,
                binding=binding,
                token_ref=token_ref,
            )
            self._emit(AuthenticationEventType.FAILURE, decision, now)
            return decision

        decision = self._decision(
            True,
            AuthenticationReason.STEP_UP_ALLOWED,
            binding=state.binding,
            token_ref=token_ref,
        )
        self._emit(AuthenticationEventType.SUCCESS, decision, now)
        return decision

    def revoke(self) -> None:
        now = self._now()
        if self._revoked:
            return
        self._revoked = True
        decision = self._decision(False, AuthenticationReason.REVOKED)
        self._emit(AuthenticationEventType.REVOCATION, decision, now)

    def _now(self) -> datetime:
        now = self._clock()
        _require_utc(now, "clock result")
        return now

    @staticmethod
    def _decision(
        allowed: bool,
        reason: AuthenticationReason,
        *,
        binding: AuthenticationBinding | None = None,
        challenge_ref: str | None = None,
        token_ref: str | None = None,
    ) -> AuthenticationDecision:
        return AuthenticationDecision(
            allowed=allowed,
            reason=reason,
            required=True,
            binding=binding,
            challenge_ref=challenge_ref,
            token_ref=token_ref,
        )

    def _emit(
        self,
        event_type: AuthenticationEventType,
        decision: AuthenticationDecision,
        timestamp: datetime,
    ) -> None:
        if self._event_sink is not None:
            self._event_sink(AuthenticationEvent(event_type, decision, timestamp))


def answer_challenge(
    challenge: AuthenticationChallenge,
    verifier: SecretStr,
) -> SecretStr:
    """Create a typed HMAC response without exposing it through repr."""

    if not isinstance(challenge, AuthenticationChallenge):
        raise TypeError("challenge must be an AuthenticationChallenge")
    if not isinstance(verifier, SecretStr):
        raise TypeError("Authentication verifier must be a SecretStr")
    secret = verifier.get_secret_value()
    if not secret:
        raise ValueError("Authentication verifier must be non-empty")
    key = hashlib.sha256(secret.encode("utf-8")).digest()
    response = hmac.digest(key, _challenge_envelope(challenge), "sha256").hex()
    return SecretStr(response)


class ServiceStepUpProvider:
    """Mint an exact-action proof from one typed service/test verifier."""

    def __init__(
        self,
        manager: AuthenticationManager,
        verifier: SecretStr,
    ) -> None:
        if not isinstance(manager, AuthenticationManager):
            raise TypeError("manager must be an AuthenticationManager")
        if not isinstance(verifier, SecretStr):
            raise TypeError("Authentication verifier must be a SecretStr")
        if not verifier.get_secret_value():
            raise ValueError("Authentication verifier must be non-empty")
        self._manager = manager
        self._verifier = verifier

    def __call__(self, binding: AuthenticationBinding) -> StepUpToken | None:
        issue = self._manager.issue_challenge(binding)
        if issue.challenge is None:
            return None
        response = answer_challenge(issue.challenge, self._verifier)
        return self._manager.complete_challenge(issue.challenge, response).token


def not_required_decision() -> AuthenticationDecision:
    return AuthenticationDecision(
        allowed=True,
        reason=AuthenticationReason.NOT_REQUIRED,
        required=False,
    )


def denied_authentication(
    reason: AuthenticationReason,
    *,
    binding: AuthenticationBinding | None = None,
) -> AuthenticationDecision:
    if reason in {
        AuthenticationReason.NOT_REQUIRED,
        AuthenticationReason.CHALLENGE_ISSUED,
        AuthenticationReason.AUTHENTICATED,
        AuthenticationReason.STEP_UP_ALLOWED,
    }:
        raise ValueError("Denied authentication requires a denial reason")
    return AuthenticationDecision(
        allowed=False,
        reason=reason,
        required=True,
        binding=binding,
    )


def _challenge_envelope(challenge: AuthenticationChallenge) -> bytes:
    payload = {
        "challenge_id": challenge.challenge_id.get_secret_value(),
        "nonce": challenge.nonce.get_secret_value(),
        "binding": challenge.binding.to_metadata(),
        "issued_at": challenge.issued_at.isoformat(),
        "expires_at": challenge.expires_at.isoformat(),
    }
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
