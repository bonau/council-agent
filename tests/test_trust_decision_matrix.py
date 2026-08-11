"""Exhaustive unit tests for the pure trust-decision matrix contract."""

from __future__ import annotations

import json
from dataclasses import replace

import pytest

from council_agent.security.decision import (
    TRUST_DECISION_MATRIX_VERSION,
    ActionRisk,
    AuthenticationState,
    DecisionVector,
    GrantState,
    InteractionState,
    PolicyState,
    ScopeState,
    TrustDecisionOutcome,
    TrustDecisionReason,
    evaluate_decision,
)


def _vector(**updates: object) -> DecisionVector:
    values: dict[str, object] = {
        "policy": PolicyState.ALLOWED,
        "scope": ScopeState.ALLOWED,
        "authentication": AuthenticationState.NOT_REQUIRED,
        "grant": GrantState.NOT_REQUIRED,
        "risk": ActionRisk.HIGH_RISK,
        "interaction": InteractionState.AUTO_APPROVED,
    }
    values.update(updates)
    return DecisionVector(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("state", "reason"),
    [
        (PolicyState.DENIED, TrustDecisionReason.POLICY_DENIED),
        (PolicyState.NOT_ALLOWED, TrustDecisionReason.POLICY_NOT_ALLOWED),
    ],
)
def test_policy_denials_win_over_every_later_denial(
    state: PolicyState,
    reason: TrustDecisionReason,
) -> None:
    decision = evaluate_decision(
        _vector(
            policy=state,
            scope=ScopeState.PRINCIPAL_MISSING,
            authentication=AuthenticationState.REVOKED,
            grant=GrantState.REVOKED,
            risk=ActionRisk.UNRECOGNIZED,
            interaction=InteractionState.AUTO_APPROVED,
        )
    )

    assert decision.outcome is TrustDecisionOutcome.DENY
    assert decision.reason is reason


@pytest.mark.parametrize(
    "state",
    [state for state in ScopeState if state is not ScopeState.ALLOWED],
)
def test_every_scope_denial_wins_over_auth_grant_and_auto(
    state: ScopeState,
) -> None:
    decision = evaluate_decision(
        _vector(
            scope=state,
            authentication=AuthenticationState.EXPIRED,
            grant=GrantState.EXPIRED,
            interaction=InteractionState.AUTO_APPROVED,
        )
    )

    assert decision.outcome is TrustDecisionOutcome.DENY
    assert decision.reason.value == state.value


@pytest.mark.parametrize(
    "state",
    [
        state
        for state in AuthenticationState
        if state
        not in {
            AuthenticationState.NOT_REQUIRED,
            AuthenticationState.SATISFIED,
        }
    ],
)
def test_every_authentication_denial_wins_over_grant_and_auto(
    state: AuthenticationState,
) -> None:
    decision = evaluate_decision(
        _vector(
            authentication=state,
            grant=GrantState.INVALID,
            interaction=InteractionState.AUTO_APPROVED,
        )
    )

    assert decision.outcome is TrustDecisionOutcome.DENY
    assert decision.reason.value == state.value


@pytest.mark.parametrize(
    "state",
    [
        state
        for state in GrantState
        if state not in {GrantState.NOT_REQUIRED, GrantState.VALID}
    ],
)
def test_every_grant_denial_wins_over_auto(state: GrantState) -> None:
    decision = evaluate_decision(
        _vector(
            authentication=AuthenticationState.SATISFIED,
            grant=state,
            interaction=InteractionState.AUTO_APPROVED,
        )
    )

    assert decision.outcome is TrustDecisionOutcome.DENY
    assert decision.reason.value == state.value


@pytest.mark.parametrize(
    ("interaction", "outcome", "reason"),
    [
        (
            InteractionState.PENDING,
            TrustDecisionOutcome.REQUIRE_CONFIRMATION,
            TrustDecisionReason.CONFIRMATION_REQUIRED,
        ),
        (
            InteractionState.DENIED,
            TrustDecisionOutcome.DENY,
            TrustDecisionReason.CONFIRMATION_DENIED,
        ),
        (
            InteractionState.REFUSED,
            TrustDecisionOutcome.DENY,
            TrustDecisionReason.CONFIRMATION_REFUSED,
        ),
        (
            InteractionState.AUTO_APPROVED,
            TrustDecisionOutcome.ALLOW,
            TrustDecisionReason.ALLOWED,
        ),
        (
            InteractionState.APPROVED,
            TrustDecisionOutcome.ALLOW,
            TrustDecisionReason.ALLOWED,
        ),
        (
            InteractionState.COMPAT_ALLOW,
            TrustDecisionOutcome.ALLOW,
            TrustDecisionReason.ALLOWED,
        ),
    ],
)
@pytest.mark.parametrize("risk", [ActionRisk.MUTATE, ActionRisk.HIGH_RISK])
def test_risk_reaches_interaction_only_after_authority_passes(
    interaction: InteractionState,
    outcome: TrustDecisionOutcome,
    reason: TrustDecisionReason,
    risk: ActionRisk,
) -> None:
    decision = evaluate_decision(
        _vector(
            authentication=AuthenticationState.SATISFIED,
            grant=GrantState.VALID,
            risk=risk,
            interaction=interaction,
        )
    )

    assert decision.outcome is outcome
    assert decision.reason is reason


def test_read_allows_without_interaction() -> None:
    decision = evaluate_decision(
        _vector(
            risk=ActionRisk.READ,
            interaction=InteractionState.NOT_REQUIRED,
        )
    )

    assert decision.outcome is TrustDecisionOutcome.ALLOW
    assert decision.reason is TrustDecisionReason.ALLOWED


def test_unrecognized_risk_fails_closed_before_interaction() -> None:
    decision = evaluate_decision(
        _vector(
            risk=ActionRisk.UNRECOGNIZED,
            interaction=InteractionState.AUTO_APPROVED,
        )
    )

    assert decision.outcome is TrustDecisionOutcome.DENY
    assert decision.reason is TrustDecisionReason.ACTION_RISK_UNRECOGNIZED


def test_complete_vector_and_result_are_stable_json_evidence() -> None:
    vector = _vector(
        authentication=AuthenticationState.SATISFIED,
        grant=GrantState.VALID,
        interaction=InteractionState.APPROVED,
    )

    first = evaluate_decision(vector)
    second = evaluate_decision(replace(vector))
    encoded = json.dumps(first.to_metadata(), sort_keys=True)

    assert first == second
    assert first.matrix_version == TRUST_DECISION_MATRIX_VERSION == 2
    assert first.to_metadata() == {
        "matrix_version": 2,
        "outcome": "allow",
        "reason": "decision_allowed",
        "vector": {
            "policy": "policy_allowed",
            "scope": "scope_allowed",
            "authentication": "step_up_allowed",
            "grant": "trust_grant_allowed",
            "risk": "high_risk",
            "interaction": "approved",
        },
    }
    for forbidden in (
        "principal-id-secret",
        "resource-secret",
        "credential-secret",
        "challenge-secret",
        "token-secret",
        "grant-id-secret",
    ):
        assert forbidden not in encoded


@pytest.mark.parametrize(
    ("field", "value", "expected"),
    [
        ("policy", "policy_allowed", "PolicyState"),
        ("scope", "scope_allowed", "ScopeState"),
        ("authentication", "authentication_not_required", "AuthenticationState"),
        ("grant", "trust_grant_not_required", "GrantState"),
        ("risk", "read", "ActionRisk"),
        ("interaction", "not_required", "InteractionState"),
    ],
)
def test_vector_rejects_untyped_states(
    field: str,
    value: str,
    expected: str,
) -> None:
    with pytest.raises(TypeError, match=expected):
        _vector(**{field: value})


def test_incoherent_interaction_combinations_are_rejected() -> None:
    # Matrix v2 allows read + interaction (Trust Tier 0). Mutate still needs
    # an interaction disposition.
    allowed = evaluate_decision(
        _vector(
            risk=ActionRisk.READ,
            interaction=InteractionState.AUTO_APPROVED,
        )
    )
    assert allowed.outcome.value == "allow"

    with pytest.raises(ValueError, match="require interaction"):
        evaluate_decision(
            _vector(
                risk=ActionRisk.MUTATE,
                interaction=InteractionState.NOT_REQUIRED,
            )
        )


def test_evaluator_rejects_non_vector_input() -> None:
    with pytest.raises(TypeError, match="DecisionVector"):
        evaluate_decision(object())  # type: ignore[arg-type]
