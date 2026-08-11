"""Versioned, pure trust-decision matrix contract."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

TRUST_DECISION_MATRIX_VERSION = 1


class PolicyState(str, Enum):
    """Normalized restrict-only policy disposition."""

    ALLOWED = "policy_allowed"
    DENIED = "policy_denied"
    NOT_ALLOWED = "policy_not_allowed"


class ScopeState(str, Enum):
    """Normalized principal and scope disposition."""

    ALLOWED = "scope_allowed"
    PRINCIPAL_MISSING = "principal_missing"
    PRINCIPAL_REVOKED = "principal_revoked"
    PRINCIPAL_INVALID = "principal_invalid"
    PRINCIPAL_MISMATCH = "principal_mismatch"
    INSUFFICIENT = "scope_insufficient"


class AuthenticationState(str, Enum):
    """Normalized exact-action authentication disposition."""

    NOT_REQUIRED = "authentication_not_required"
    SATISFIED = "step_up_allowed"
    MISSING = "authentication_missing"
    INVALID = "authentication_invalid"
    FAILED = "authentication_failed"
    EXPIRED = "authentication_expired"
    REVOKED = "authentication_revoked"
    REPLAY = "authentication_replay"
    BINDING_MISMATCH = "authentication_binding_mismatch"
    PROVIDER_ERROR = "authentication_provider_error"


class GrantState(str, Enum):
    """Normalized trust-grant disposition for current or future callers."""

    NOT_REQUIRED = "trust_grant_not_required"
    VALID = "trust_grant_allowed"
    MISSING = "trust_grant_not_found"
    INVALID = "trust_grant_invalid"
    REVOKED = "trust_grant_revoked"
    EXPIRED = "trust_grant_expired"
    PRINCIPAL_SCOPE_INSUFFICIENT = "trust_principal_scope_insufficient"
    GRANT_SCOPE_INSUFFICIENT = "trust_grant_scope_insufficient"


class ActionRisk(str, Enum):
    """Canonical risk used only after authority gates pass."""

    READ = "read"
    MUTATE = "mutate"
    HIGH_RISK = "high_risk"
    UNRECOGNIZED = "unrecognized"


class InteractionState(str, Enum):
    """Normalized result of interaction handling, never authority."""

    NOT_REQUIRED = "not_required"
    PENDING = "pending"
    AUTO_APPROVED = "auto"
    APPROVED = "approved"
    DENIED = "denied"
    REFUSED = "refused"
    COMPAT_ALLOW = "compat_allow"


class TrustDecisionOutcome(str, Enum):
    """Only outcomes emitted by the matrix."""

    DENY = "deny"
    REQUIRE_CONFIRMATION = "require_confirmation"
    ALLOW = "allow"


class TrustDecisionReason(str, Enum):
    """Stable winning reasons for matrix version 1."""

    POLICY_DENIED = PolicyState.DENIED.value
    POLICY_NOT_ALLOWED = PolicyState.NOT_ALLOWED.value
    PRINCIPAL_MISSING = ScopeState.PRINCIPAL_MISSING.value
    PRINCIPAL_REVOKED = ScopeState.PRINCIPAL_REVOKED.value
    PRINCIPAL_INVALID = ScopeState.PRINCIPAL_INVALID.value
    PRINCIPAL_MISMATCH = ScopeState.PRINCIPAL_MISMATCH.value
    SCOPE_INSUFFICIENT = ScopeState.INSUFFICIENT.value
    AUTHENTICATION_MISSING = AuthenticationState.MISSING.value
    AUTHENTICATION_INVALID = AuthenticationState.INVALID.value
    AUTHENTICATION_FAILED = AuthenticationState.FAILED.value
    AUTHENTICATION_EXPIRED = AuthenticationState.EXPIRED.value
    AUTHENTICATION_REVOKED = AuthenticationState.REVOKED.value
    AUTHENTICATION_REPLAY = AuthenticationState.REPLAY.value
    AUTHENTICATION_BINDING_MISMATCH = AuthenticationState.BINDING_MISMATCH.value
    AUTHENTICATION_PROVIDER_ERROR = AuthenticationState.PROVIDER_ERROR.value
    TRUST_GRANT_MISSING = GrantState.MISSING.value
    TRUST_GRANT_INVALID = GrantState.INVALID.value
    TRUST_GRANT_REVOKED = GrantState.REVOKED.value
    TRUST_GRANT_EXPIRED = GrantState.EXPIRED.value
    TRUST_PRINCIPAL_SCOPE_INSUFFICIENT = (
        GrantState.PRINCIPAL_SCOPE_INSUFFICIENT.value
    )
    TRUST_GRANT_SCOPE_INSUFFICIENT = GrantState.GRANT_SCOPE_INSUFFICIENT.value
    ACTION_RISK_UNRECOGNIZED = "action_risk_unrecognized"
    CONFIRMATION_REQUIRED = "confirmation_required"
    CONFIRMATION_DENIED = "confirmation_denied"
    CONFIRMATION_REFUSED = "confirmation_refused"
    ALLOWED = "decision_allowed"


@dataclass(frozen=True)
class DecisionVector:
    """Complete non-secret input to trust-decision matrix version 1."""

    policy: PolicyState
    scope: ScopeState
    authentication: AuthenticationState
    grant: GrantState
    risk: ActionRisk
    interaction: InteractionState

    def __post_init__(self) -> None:
        fields = (
            ("policy", self.policy, PolicyState),
            ("scope", self.scope, ScopeState),
            ("authentication", self.authentication, AuthenticationState),
            ("grant", self.grant, GrantState),
            ("risk", self.risk, ActionRisk),
            ("interaction", self.interaction, InteractionState),
        )
        for name, value, expected in fields:
            if not isinstance(value, expected):
                raise TypeError(f"Decision vector {name} must be {expected.__name__}")

    def to_metadata(self) -> dict[str, str]:
        """Return the complete JSON-safe, credential-free vector."""

        return {
            "policy": self.policy.value,
            "scope": self.scope.value,
            "authentication": self.authentication.value,
            "grant": self.grant.value,
            "risk": self.risk.value,
            "interaction": self.interaction.value,
        }


@dataclass(frozen=True)
class TrustDecision:
    """One deterministic matrix result and its complete input vector."""

    outcome: TrustDecisionOutcome
    reason: TrustDecisionReason
    vector: DecisionVector
    matrix_version: int = TRUST_DECISION_MATRIX_VERSION

    def to_metadata(self) -> dict[str, Any]:
        """Return normalized evidence safe for result/session/audit storage."""

        return {
            "matrix_version": self.matrix_version,
            "outcome": self.outcome.value,
            "reason": self.reason.value,
            "vector": self.vector.to_metadata(),
        }


_POLICY_DENIALS = {
    PolicyState.DENIED: TrustDecisionReason.POLICY_DENIED,
    PolicyState.NOT_ALLOWED: TrustDecisionReason.POLICY_NOT_ALLOWED,
}
_SCOPE_DENIALS = {
    state: TrustDecisionReason(state.value)
    for state in ScopeState
    if state is not ScopeState.ALLOWED
}
_AUTHENTICATION_DENIALS = {
    state: TrustDecisionReason(state.value)
    for state in AuthenticationState
    if state
    not in {
        AuthenticationState.NOT_REQUIRED,
        AuthenticationState.SATISFIED,
    }
}
_GRANT_DENIALS = {
    state: TrustDecisionReason(state.value)
    for state in GrantState
    if state not in {GrantState.NOT_REQUIRED, GrantState.VALID}
}


def evaluate_decision(vector: DecisionVector) -> TrustDecision:
    """Evaluate one complete vector using immutable schema-v1 precedence."""

    if not isinstance(vector, DecisionVector):
        raise TypeError("vector must be a DecisionVector")

    policy_reason = _POLICY_DENIALS.get(vector.policy)
    if policy_reason is not None:
        return _decision(TrustDecisionOutcome.DENY, policy_reason, vector)

    scope_reason = _SCOPE_DENIALS.get(vector.scope)
    if scope_reason is not None:
        return _decision(TrustDecisionOutcome.DENY, scope_reason, vector)

    authentication_reason = _AUTHENTICATION_DENIALS.get(vector.authentication)
    if authentication_reason is not None:
        return _decision(
            TrustDecisionOutcome.DENY,
            authentication_reason,
            vector,
        )

    grant_reason = _GRANT_DENIALS.get(vector.grant)
    if grant_reason is not None:
        return _decision(TrustDecisionOutcome.DENY, grant_reason, vector)

    if vector.risk is ActionRisk.UNRECOGNIZED:
        return _decision(
            TrustDecisionOutcome.DENY,
            TrustDecisionReason.ACTION_RISK_UNRECOGNIZED,
            vector,
        )

    if vector.risk is ActionRisk.READ:
        if vector.interaction is not InteractionState.NOT_REQUIRED:
            raise ValueError("Read-risk decisions cannot use interaction authority")
        return _decision(
            TrustDecisionOutcome.ALLOW,
            TrustDecisionReason.ALLOWED,
            vector,
        )

    if vector.interaction is InteractionState.PENDING:
        return _decision(
            TrustDecisionOutcome.REQUIRE_CONFIRMATION,
            TrustDecisionReason.CONFIRMATION_REQUIRED,
            vector,
        )
    if vector.interaction is InteractionState.DENIED:
        return _decision(
            TrustDecisionOutcome.DENY,
            TrustDecisionReason.CONFIRMATION_DENIED,
            vector,
        )
    if vector.interaction is InteractionState.REFUSED:
        return _decision(
            TrustDecisionOutcome.DENY,
            TrustDecisionReason.CONFIRMATION_REFUSED,
            vector,
        )
    if vector.interaction in {
        InteractionState.AUTO_APPROVED,
        InteractionState.APPROVED,
        InteractionState.COMPAT_ALLOW,
    }:
        return _decision(
            TrustDecisionOutcome.ALLOW,
            TrustDecisionReason.ALLOWED,
            vector,
        )
    raise ValueError("Mutate and high-risk decisions require interaction disposition")


def _decision(
    outcome: TrustDecisionOutcome,
    reason: TrustDecisionReason,
    vector: DecisionVector,
) -> TrustDecision:
    return TrustDecision(outcome=outcome, reason=reason, vector=vector)
