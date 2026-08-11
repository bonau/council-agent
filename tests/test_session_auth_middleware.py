"""Dispatcher integration tests for fresh session step-up authentication."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from unittest import mock

import pytest
from pydantic import SecretStr

from council_agent.crews.execution_tools import build_execution_tools
from council_agent.security.authentication import (
    AuthenticationBinding,
    AuthenticationManager,
    AuthenticationReason,
    ServiceStepUpProvider,
    StepUpToken,
    answer_challenge,
)
from council_agent.security.audit import AuditLogger, load_audit_events
from council_agent.security.confirm import ConfirmMode, ConfirmationPolicy
from council_agent.security.middleware import (
    SecurityContext,
    security_context,
    without_security_context,
)
from council_agent.security.policy import CouncilPolicy
from council_agent.security.principal import Principal, full_scope_principal
from council_agent.tools import run_command


@pytest.fixture(autouse=True)
def no_default_security_context() -> None:
    with without_security_context():
        yield


def _token_for(
    manager: AuthenticationManager,
    verifier: SecretStr,
    binding: AuthenticationBinding,
) -> StepUpToken:
    issue = manager.issue_challenge(binding)
    assert issue.challenge is not None
    completion = manager.complete_challenge(
        issue.challenge,
        answer_challenge(issue.challenge, verifier),
    )
    assert completion.token is not None
    return completion.token


def _context(
    tmp_path: Path,
    principal: Principal,
    *,
    manager: AuthenticationManager | None = None,
    provider=None,
    session_id: str = "middleware-auth-session",
    confirmation: ConfirmationPolicy | None = None,
    policy: CouncilPolicy | None = None,
    audit_logger: AuditLogger | None = None,
) -> SecurityContext:
    return SecurityContext.create(
        tmp_path,
        principal=principal,
        session_id=session_id,
        authentication_manager=manager,
        step_up_provider=provider,
        require_high_risk_step_up=True,
        confirmation=confirmation or ConfirmationPolicy(mode=ConfirmMode.AUTO),
        policy=policy,
        audit_logger=audit_logger,
    )


def test_high_risk_action_without_auth_denies_before_handler_and_process(
    tmp_path: Path,
) -> None:
    marker = tmp_path / "marker"
    marker.mkdir()
    principal = full_scope_principal("missing-auth", issuer="pytest")
    context = _context(tmp_path, principal)

    with (
        security_context(context),
        mock.patch("council_agent.tools.shell._authorize_action") as lower_gate,
        mock.patch("council_agent.tools.shell.subprocess.run") as process,
    ):
        result = run_command("rm -rf marker")

    assert result.success is False
    assert result.metadata["rejection_reason"] == "authentication_missing"
    assert (
        result.metadata["session_authentication"]["reason"]
        == "authentication_missing"
    )
    assert result.metadata["session_authentication"]["required"] is True
    assert lower_gate.call_count == 0
    assert process.call_count == 0
    assert marker.is_dir()


def test_crew_wrapper_cannot_bypass_missing_step_up(tmp_path: Path) -> None:
    marker = tmp_path / "marker"
    marker.mkdir()
    context = _context(
        tmp_path,
        full_scope_principal("crew-missing-auth", issuer="pytest"),
    )
    run_tool = {tool.name: tool for tool in build_execution_tools()}["run_command"]

    with (
        security_context(context),
        mock.patch("council_agent.tools.shell.subprocess.run") as process,
    ):
        result = run_tool.run(command="rm -rf marker")

    assert result.startswith("ERROR:")
    assert process.call_count == 0
    assert marker.is_dir()
    assert context.tracker.summaries == []


def test_service_step_up_allows_high_risk_action_then_confirmation(
    tmp_path: Path,
) -> None:
    marker = tmp_path / "marker"
    marker.mkdir()
    verifier = SecretStr("middleware-service-verifier")
    manager = AuthenticationManager(verifier)
    context = _context(
        tmp_path,
        full_scope_principal("service-auth", issuer="pytest"),
        manager=manager,
        provider=ServiceStepUpProvider(manager, verifier),
    )

    with security_context(context):
        result = run_command("rm -rf marker")

    assert result.success is True
    assert not marker.exists()
    assert (
        result.metadata["session_authentication"]["reason"] == "step_up_allowed"
    )
    assert result.metadata["session_authentication"]["required"] is True


def test_ordinary_action_does_not_require_authentication(tmp_path: Path) -> None:
    context = _context(
        tmp_path,
        full_scope_principal("ordinary-action", issuer="pytest"),
    )

    with security_context(context):
        result = run_command("echo ordinary")

    assert result.success is True
    assert (
        result.metadata["session_authentication"]["reason"]
        == "authentication_not_required"
    )
    assert result.metadata["session_authentication"]["required"] is False


@pytest.mark.parametrize(
    "wrong_binding",
    [
        "principal",
        "workspace",
        "session",
        "purpose",
        "action",
    ],
)
def test_wrong_bound_proof_denies_without_process(
    tmp_path: Path,
    wrong_binding: str,
) -> None:
    marker = tmp_path / "marker"
    marker.mkdir()
    principal = full_scope_principal("binding-user", issuer="pytest")
    verifier = SecretStr("binding-middleware-verifier")
    manager = AuthenticationManager(verifier)
    expected = AuthenticationBinding.for_action(
        principal,
        tmp_path,
        "target-session",
        "run_command",
        {"command": "rm -rf marker"},
    )
    if wrong_binding == "principal":
        bound = AuthenticationBinding.for_action(
            full_scope_principal("other-user", issuer="pytest"),
            tmp_path,
            "target-session",
            "run_command",
            {"command": "rm -rf marker"},
        )
    elif wrong_binding == "workspace":
        other_workspace = tmp_path / "other"
        other_workspace.mkdir()
        bound = AuthenticationBinding.for_action(
            principal,
            other_workspace,
            "target-session",
            "run_command",
            {"command": "rm -rf marker"},
        )
    elif wrong_binding == "session":
        bound = AuthenticationBinding.for_action(
            principal,
            tmp_path,
            "other-session",
            "run_command",
            {"command": "rm -rf marker"},
        )
    elif wrong_binding == "purpose":
        bound = AuthenticationBinding(
            principal_ref=expected.principal_ref,
            workspace_ref=expected.workspace_ref,
            session_id=expected.session_id,
            purpose="other-purpose",
            action_ref=expected.action_ref,
        )
    else:
        bound = AuthenticationBinding.for_action(
            principal,
            tmp_path,
            "target-session",
            "run_command",
            {"command": "rm -rf other-marker"},
        )
    token = _token_for(manager, verifier, bound)
    context = _context(
        tmp_path,
        principal,
        manager=manager,
        provider=lambda _binding: token,
        session_id="target-session",
    )

    with (
        security_context(context),
        mock.patch("council_agent.tools.shell.subprocess.run") as process,
    ):
        result = run_command("rm -rf marker")

    assert result.success is False
    assert (
        result.metadata["rejection_reason"]
        == AuthenticationReason.BINDING_MISMATCH.value
    )
    assert process.call_count == 0
    assert marker.is_dir()


def test_replayed_expired_and_revoked_proofs_deny_without_process(
    tmp_path: Path,
) -> None:
    principal = full_scope_principal("lifecycle-user", issuer="pytest")
    verifier = SecretStr("lifecycle-middleware-verifier")
    binding = AuthenticationBinding.for_action(
        principal,
        tmp_path,
        "lifecycle-session",
        "run_command",
        {"command": "rm -rf marker"},
    )

    replay_manager = AuthenticationManager(verifier)
    replay_token = _token_for(replay_manager, verifier, binding)
    assert replay_manager.consume_step_up(replay_token, binding).allowed is True

    expired_manager = AuthenticationManager(
        verifier,
        token_ttl=timedelta(microseconds=1),
    )
    expired_token = _token_for(expired_manager, verifier, binding)

    revoked_manager = AuthenticationManager(verifier)
    revoked_token = _token_for(revoked_manager, verifier, binding)
    revoked_manager.revoke()

    cases = [
        (
            replay_manager,
            replay_token,
            AuthenticationReason.REPLAY.value,
        ),
        (
            expired_manager,
            expired_token,
            AuthenticationReason.EXPIRED.value,
        ),
        (
            revoked_manager,
            revoked_token,
            AuthenticationReason.REVOKED.value,
        ),
    ]
    for manager, token, expected_reason in cases:
        marker = tmp_path / "marker"
        marker.mkdir(exist_ok=True)
        context = _context(
            tmp_path,
            principal,
            manager=manager,
            provider=lambda _binding, proof=token: proof,
            session_id="lifecycle-session",
        )
        with (
            security_context(context),
            mock.patch("council_agent.tools.shell.subprocess.run") as process,
        ):
            result = run_command("rm -rf marker")
        assert result.metadata["rejection_reason"] == expected_reason
        assert process.call_count == 0
        assert marker.is_dir()


def test_authentication_does_not_override_confirmation_or_policy(
    tmp_path: Path,
) -> None:
    principal = full_scope_principal("lower-gates", issuer="pytest")
    verifier = SecretStr("lower-gates-verifier")

    refused_manager = AuthenticationManager(verifier)
    refused_context = _context(
        tmp_path,
        principal,
        manager=refused_manager,
        provider=ServiceStepUpProvider(refused_manager, verifier),
        confirmation=ConfirmationPolicy(mode=ConfirmMode.REFUSE),
    )
    with (
        security_context(refused_context),
        mock.patch("council_agent.tools.shell.subprocess.run") as process,
    ):
        refused = run_command("rm -rf marker")
    assert refused.success is False
    assert refused.metadata["confirmation"] == "refused"
    assert process.call_count == 0

    policy_manager = AuthenticationManager(verifier)
    policy_context = _context(
        tmp_path,
        principal,
        manager=policy_manager,
        provider=ServiceStepUpProvider(policy_manager, verifier),
        policy=CouncilPolicy(
            schema_version=1,
            denied_commands=["rm *"],
        ),
    )
    with (
        security_context(policy_context),
        mock.patch("council_agent.tools.shell.subprocess.run") as process,
    ):
        denied = run_command("rm -rf marker")
    assert denied.success is False
    assert denied.metadata["policy_decision"] == "denied"
    assert process.call_count == 0


def test_authentication_metadata_is_masked_in_correlated_audit(
    tmp_path: Path,
) -> None:
    raw_principal = "sk-or-v1-session-auth-principal"
    raw_verifier = "audit-session-auth-verifier"
    principal = full_scope_principal(raw_principal, issuer="pytest")
    verifier = SecretStr(raw_verifier)
    manager = AuthenticationManager(verifier)
    audit_path = tmp_path / "audit" / "events.jsonl"
    context = _context(
        tmp_path,
        principal,
        manager=manager,
        provider=ServiceStepUpProvider(manager, verifier),
        audit_logger=AuditLogger(
            audit_path,
            session_id="middleware-auth-session",
        ),
    )
    marker = tmp_path / "marker"
    marker.mkdir()

    with security_context(context):
        result = run_command("rm -rf marker")

    raw = audit_path.read_text(encoding="utf-8")
    events = load_audit_events(audit_path)
    assert result.success is True
    assert [event.phase for event in events] == ["attempt", "result"]
    assert all(
        event.metadata["session_authentication"]["reason"] == "step_up_allowed"
        for event in events
    )
    assert raw_principal not in raw
    assert raw_verifier not in raw
    assert events[1].attempt_event_id == events[0].event_id
