"""Unit tests for process-local session step-up authentication."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from pydantic import SecretStr

from council_agent.security.authentication import (
    AuthenticationBinding,
    AuthenticationChallenge,
    AuthenticationEvent,
    AuthenticationEventType,
    AuthenticationManager,
    AuthenticationReason,
    ServiceStepUpProvider,
    StepUpToken,
    answer_challenge,
)
from council_agent.security.principal import full_scope_principal


class MutableClock:
    def __init__(self) -> None:
        self.value = datetime(2026, 8, 11, 18, 0, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.value

    def advance(self, delta: timedelta) -> None:
        self.value += delta


@pytest.fixture
def binding(tmp_path: Path) -> AuthenticationBinding:
    return AuthenticationBinding.for_action(
        full_scope_principal("auth-user", issuer="pytest"),
        tmp_path,
        "session-auth-test",
        "run_command",
        {"command": "rm -rf marker"},
    )


def _complete(
    manager: AuthenticationManager,
    verifier: SecretStr,
    binding: AuthenticationBinding,
) -> tuple[AuthenticationChallenge, StepUpToken]:
    issue = manager.issue_challenge(binding)
    assert issue.challenge is not None
    completion = manager.complete_challenge(
        issue.challenge,
        answer_challenge(issue.challenge, verifier),
    )
    assert completion.token is not None
    return issue.challenge, completion.token


def test_challenge_and_token_success_are_exact_bound_and_one_use(
    binding: AuthenticationBinding,
) -> None:
    verifier = SecretStr("unit-test-verifier-secret")
    events: list[AuthenticationEvent] = []
    manager = AuthenticationManager(verifier, event_sink=events.append)

    challenge, token = _complete(manager, verifier, binding)
    decision = manager.consume_step_up(token, binding)
    challenge_replay = manager.complete_challenge(
        challenge,
        answer_challenge(challenge, verifier),
    )
    token_replay = manager.consume_step_up(token, binding)

    assert decision.allowed is True
    assert decision.reason is AuthenticationReason.STEP_UP_ALLOWED
    assert challenge_replay.token is None
    assert challenge_replay.decision.reason is AuthenticationReason.REPLAY
    assert token_replay.reason is AuthenticationReason.REPLAY
    assert [event.event_type for event in events] == [
        AuthenticationEventType.SUCCESS,
        AuthenticationEventType.SUCCESS,
        AuthenticationEventType.REPLAY,
        AuthenticationEventType.REPLAY,
    ]


def test_failed_challenge_is_consumed_before_credential_comparison(
    binding: AuthenticationBinding,
) -> None:
    verifier = SecretStr("correct-verifier")
    manager = AuthenticationManager(verifier)
    issue = manager.issue_challenge(binding)
    assert issue.challenge is not None

    failed = manager.complete_challenge(
        issue.challenge,
        SecretStr("incorrect-response"),
    )
    replayed = manager.complete_challenge(
        issue.challenge,
        answer_challenge(issue.challenge, verifier),
    )

    assert failed.token is None
    assert failed.decision.reason is AuthenticationReason.FAILED
    assert replayed.token is None
    assert replayed.decision.reason is AuthenticationReason.REPLAY


def test_challenge_binding_mismatch_consumes_challenge(
    binding: AuthenticationBinding,
) -> None:
    verifier = SecretStr("binding-verifier")
    manager = AuthenticationManager(verifier)
    issue = manager.issue_challenge(binding)
    assert issue.challenge is not None
    wrong_binding = replace(binding, session_id="wrong-session")
    forged = replace(issue.challenge, binding=wrong_binding)

    mismatch = manager.complete_challenge(
        forged,
        answer_challenge(forged, verifier),
    )
    replay = manager.complete_challenge(
        issue.challenge,
        answer_challenge(issue.challenge, verifier),
    )

    assert mismatch.decision.reason is AuthenticationReason.BINDING_MISMATCH
    assert replay.decision.reason is AuthenticationReason.REPLAY


@pytest.mark.parametrize(
    ("field_name", "replacement"),
    [
        ("principal_ref", "sha256:wrong-principal"),
        ("workspace_ref", "sha256:wrong-workspace"),
        ("session_id", "wrong-session"),
        ("purpose", "wrong-purpose"),
        ("action_ref", "sha256:wrong-action"),
    ],
)
def test_token_binding_mismatch_is_denied_then_replayed(
    binding: AuthenticationBinding,
    field_name: str,
    replacement: str,
) -> None:
    verifier = SecretStr("token-binding-verifier")
    manager = AuthenticationManager(verifier)
    _challenge, token = _complete(manager, verifier, binding)
    wrong = replace(binding, **{field_name: replacement})

    mismatch = manager.consume_step_up(token, wrong)
    replay = manager.consume_step_up(token, binding)

    assert mismatch.reason is AuthenticationReason.BINDING_MISMATCH
    assert replay.reason is AuthenticationReason.REPLAY


def test_challenge_expiry_and_token_freshness_fail_closed(
    binding: AuthenticationBinding,
) -> None:
    verifier = SecretStr("expiry-verifier")
    clock = MutableClock()
    events: list[AuthenticationEvent] = []
    manager = AuthenticationManager(
        verifier,
        clock=clock,
        challenge_ttl=timedelta(seconds=5),
        token_ttl=timedelta(minutes=5),
        event_sink=events.append,
    )
    expired_issue = manager.issue_challenge(binding)
    assert expired_issue.challenge is not None
    clock.advance(timedelta(seconds=5))
    expired_challenge = manager.complete_challenge(
        expired_issue.challenge,
        answer_challenge(expired_issue.challenge, verifier),
    )

    fresh_issue = manager.issue_challenge(binding)
    assert fresh_issue.challenge is not None
    completion = manager.complete_challenge(
        fresh_issue.challenge,
        answer_challenge(fresh_issue.challenge, verifier),
    )
    assert completion.token is not None
    clock.advance(timedelta(seconds=61))
    stale = manager.consume_step_up(
        completion.token,
        binding,
        freshness=timedelta(seconds=60),
    )

    assert expired_challenge.decision.reason is AuthenticationReason.EXPIRED
    assert stale.reason is AuthenticationReason.EXPIRED
    assert [event.event_type for event in events].count(
        AuthenticationEventType.EXPIRY
    ) == 2


def test_absolute_token_expiry_and_clock_rollback_are_denied(
    binding: AuthenticationBinding,
) -> None:
    verifier = SecretStr("clock-verifier")
    clock = MutableClock()
    manager = AuthenticationManager(
        verifier,
        clock=clock,
        token_ttl=timedelta(seconds=5),
    )
    _challenge, expired_token = _complete(manager, verifier, binding)
    clock.advance(timedelta(seconds=5))
    assert (
        manager.consume_step_up(
            expired_token,
            binding,
            freshness=timedelta(minutes=1),
        ).reason
        is AuthenticationReason.EXPIRED
    )

    _challenge, rollback_token = _complete(manager, verifier, binding)
    clock.advance(timedelta(seconds=-1))
    assert (
        manager.consume_step_up(rollback_token, binding).reason
        is AuthenticationReason.EXPIRED
    )


def test_revoke_denies_outstanding_state_and_new_challenges(
    binding: AuthenticationBinding,
) -> None:
    verifier = SecretStr("revocation-verifier")
    events: list[AuthenticationEvent] = []
    manager = AuthenticationManager(verifier, event_sink=events.append)
    issue = manager.issue_challenge(binding)
    assert issue.challenge is not None
    _challenge, token = _complete(manager, verifier, binding)

    manager.revoke()
    completion = manager.complete_challenge(
        issue.challenge,
        answer_challenge(issue.challenge, verifier),
    )
    consumed = manager.consume_step_up(token, binding)
    new_issue = manager.issue_challenge(binding)

    assert manager.revoked is True
    assert completion.decision.reason is AuthenticationReason.REVOKED
    assert consumed.reason is AuthenticationReason.REVOKED
    assert new_issue.challenge is None
    assert new_issue.decision.reason is AuthenticationReason.REVOKED
    assert any(
        event.event_type is AuthenticationEventType.REVOCATION for event in events
    )


def test_new_manager_rejects_prior_process_challenge_and_token(
    binding: AuthenticationBinding,
) -> None:
    verifier = SecretStr("restart-verifier")
    original = AuthenticationManager(verifier)
    old_challenge, old_token = _complete(original, verifier, binding)
    restarted = AuthenticationManager(verifier)

    challenge_result = restarted.complete_challenge(
        old_challenge,
        answer_challenge(old_challenge, verifier),
    )
    token_result = restarted.consume_step_up(old_token, binding)

    assert challenge_result.decision.reason is AuthenticationReason.INVALID
    assert token_result.reason is AuthenticationReason.INVALID


def test_service_provider_uses_typed_secret_and_mints_fresh_tokens(
    binding: AuthenticationBinding,
) -> None:
    verifier = SecretStr("service-verifier")
    manager = AuthenticationManager(verifier)
    provider = ServiceStepUpProvider(manager, verifier)

    first = provider(binding)
    second = provider(binding)

    assert isinstance(first, StepUpToken)
    assert isinstance(second, StepUpToken)
    assert first.audit_ref != second.audit_ref
    assert manager.consume_step_up(first, binding).allowed is True
    assert manager.consume_step_up(second, binding).allowed is True


def test_secret_values_do_not_appear_in_repr_or_event_metadata(
    binding: AuthenticationBinding,
) -> None:
    raw_verifier = "plain-verifier-must-not-persist"
    verifier = SecretStr(raw_verifier)
    events: list[AuthenticationEvent] = []
    manager = AuthenticationManager(verifier, event_sink=events.append)
    issue = manager.issue_challenge(binding)
    assert issue.challenge is not None
    raw_challenge = issue.challenge.challenge_id.get_secret_value()
    raw_nonce = issue.challenge.nonce.get_secret_value()
    response = answer_challenge(issue.challenge, verifier)
    raw_response = response.get_secret_value()
    completion = manager.complete_challenge(issue.challenge, response)
    assert completion.token is not None
    raw_token = completion.token.value.get_secret_value()
    manager.consume_step_up(completion.token, binding)

    rendered = "\n".join(
        [
            repr(issue.challenge),
            repr(completion.token),
            json.dumps([event.to_metadata() for event in events], sort_keys=True),
        ]
    )
    for secret in (
        raw_verifier,
        raw_challenge,
        raw_nonce,
        raw_response,
        raw_token,
    ):
        assert secret not in rendered
    assert issue.challenge.audit_ref in rendered
    assert completion.token.audit_ref in rendered


def test_binding_requires_non_empty_fields_and_aware_clock(
    binding: AuthenticationBinding,
) -> None:
    with pytest.raises(ValueError, match="session_id"):
        replace(binding, session_id="")

    manager = AuthenticationManager(
        SecretStr("aware-clock-verifier"),
        clock=lambda: datetime(2026, 8, 11),
    )
    with pytest.raises(ValueError, match="timezone-aware"):
        manager.issue_challenge(binding)
