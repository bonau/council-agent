"""Sandboxed end-to-end evidence for session authentication."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

import pytest
from pydantic import SecretStr

from council_agent.config.presets import get_preset_by_name
from council_agent.llm.openrouter import OpenRouterCredential
from council_agent.orchestrator import run_council
from council_agent.sandbox.config import apply_workspace_root, init_sandbox
from council_agent.sandbox.session import SessionManager
from council_agent.security import (
    AuthenticationBinding,
    AuthenticationManager,
    AuditLogger,
    ConfirmMode,
    answer_challenge,
    authentication_audit_sink,
    default_audit_events_path,
    full_scope_principal,
    load_audit_events,
    without_security_context,
)
from council_agent.tools import run_command
from council_agent.types import (
    ExecutionResult,
    PlanArtifact,
    VerdictStatus,
    VerificationVerdict,
)

PRESETS_DIR = Path(__file__).resolve().parents[1] / "presets"
PROVIDER_CREDENTIAL = OpenRouterCredential("e2e-provider")
PRINCIPAL = full_scope_principal("session-auth-e2e", issuer="pytest")


class MutableClock:
    def __init__(self) -> None:
        self.value = datetime(2026, 8, 11, 18, 30, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.value


@pytest.fixture(autouse=True)
def no_default_security_context() -> None:
    with without_security_context():
        yield


def _run_sandboxed_high_risk(
    tmp_path: Path,
    *,
    verifier: SecretStr | None,
) -> object:
    init_sandbox(tmp_path)
    apply_workspace_root(tmp_path)
    marker = tmp_path / "marker"
    marker.mkdir()
    preset = get_preset_by_name(PRESETS_DIR, "glm-stack")
    plan = PlanArtifact(
        raw="{}",
        steps=["remove marker"],
        success_criteria=["marker removed only after authentication"],
        risks=[],
    )
    verdict = VerificationVerdict(
        status=VerdictStatus.PASS,
        raw='{"status":"PASS"}',
        issues=[],
        summary="ok",
    )
    tool_results: list[object] = []

    def _execution(*_args, **_kwargs) -> ExecutionResult:
        tool_results.append(run_command("rm -rf marker"))
        return ExecutionResult(raw="high-risk action attempted")

    with (
        mock.patch("council_agent.orchestrator.build_planning_crew"),
        mock.patch("council_agent.orchestrator.build_execution_crew"),
        mock.patch("council_agent.orchestrator.build_verification_crew"),
        mock.patch("council_agent.orchestrator.run_planning", return_value=plan),
        mock.patch(
            "council_agent.orchestrator.run_execution",
            side_effect=_execution,
        ),
        mock.patch(
            "council_agent.orchestrator.run_verification",
            return_value=verdict,
        ),
    ):
        run_council(
            "remove marker with fresh step-up",
            preset,
            PROVIDER_CREDENTIAL,
            PRINCIPAL,
            project_root=tmp_path,
            confirm_mode=ConfirmMode.AUTO,
            authentication_verifier=verifier,
        )

    assert len(tool_results) == 1
    return tool_results[0]


def test_sandboxed_service_step_up_succeeds_with_masked_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw_verifier = "sandboxed-service-verifier-must-not-persist"
    monkeypatch.chdir(tmp_path)

    result = _run_sandboxed_high_risk(
        tmp_path,
        verifier=SecretStr(raw_verifier),
    )

    assert result.success is True
    assert not (tmp_path / "marker").exists()
    events_path = default_audit_events_path(tmp_path)
    raw_audit = events_path.read_text(encoding="utf-8")
    events = load_audit_events(events_path)
    session = SessionManager.latest(tmp_path)
    assert session is not None
    raw_meta = session.meta_path.read_text(encoding="utf-8")
    raw_tools = session.tools_path.read_text(encoding="utf-8")
    assert raw_verifier not in raw_audit
    assert raw_verifier not in raw_meta
    assert raw_verifier not in raw_tools
    assert [event.tool for event in events].count("session_auth") == 3
    assert [event.tool for event in events].count("run_command") == 2
    auth_types = [
        event.metadata["session_authentication"]["event_type"]
        for event in events
        if event.tool == "session_auth"
    ]
    assert auth_types == [
        "authentication_success",
        "authentication_success",
        "authentication_revocation",
    ]
    lines = [
        json.loads(line)
        for line in raw_tools.splitlines()
        if line.strip()
    ]
    assert len(lines) == 1
    assert (
        lines[0]["metadata"]["session_authentication"]["reason"]
        == "step_up_allowed"
    )
    assert all(event.session_id == session.meta.session_id for event in events)


def test_sandboxed_yes_only_denies_without_side_effect(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    result = _run_sandboxed_high_risk(tmp_path, verifier=None)

    assert result.success is False
    assert result.metadata["rejection_reason"] == "authentication_missing"
    assert (tmp_path / "marker").is_dir()
    events = load_audit_events(default_audit_events_path(tmp_path))
    assert [event.tool for event in events] == ["run_command", "run_command"]
    assert all(
        event.metadata["session_authentication"]["reason"]
        == "authentication_missing"
        for event in events
    )
    session = SessionManager.latest(tmp_path)
    assert session is not None
    assert session.count_tool_lines() == 1


def test_durable_lifecycle_matrix_masks_all_raw_authentication_values(
    tmp_path: Path,
) -> None:
    raw_verifier = "durable-lifecycle-verifier"
    verifier = SecretStr(raw_verifier)
    audit_path = tmp_path / "audit" / "events.jsonl"
    logger = AuditLogger(audit_path, session_id="durable-auth-session")
    sink = authentication_audit_sink(
        logger,
        request_id="durable-auth-request",
        session_id="durable-auth-session",
    )
    assert sink is not None
    principal = full_scope_principal("durable-auth-user", issuer="pytest")
    binding = AuthenticationBinding.for_action(
        principal,
        tmp_path,
        "durable-auth-session",
        "run_command",
        {"command": "rm -rf marker"},
    )
    raw_values = [raw_verifier]

    success = AuthenticationManager(verifier, event_sink=sink)
    issue = success.issue_challenge(binding)
    assert issue.challenge is not None
    response = answer_challenge(issue.challenge, verifier)
    completion = success.complete_challenge(issue.challenge, response)
    assert completion.token is not None
    raw_values.extend(
        [
            issue.challenge.challenge_id.get_secret_value(),
            issue.challenge.nonce.get_secret_value(),
            response.get_secret_value(),
            completion.token.value.get_secret_value(),
        ]
    )
    assert success.consume_step_up(completion.token, binding).allowed is True
    success.consume_step_up(completion.token, binding)

    failure = AuthenticationManager(verifier, event_sink=sink)
    failed_issue = failure.issue_challenge(binding)
    assert failed_issue.challenge is not None
    raw_values.extend(
        [
            failed_issue.challenge.challenge_id.get_secret_value(),
            failed_issue.challenge.nonce.get_secret_value(),
            "wrong-response-value",
        ]
    )
    failure.complete_challenge(
        failed_issue.challenge,
        SecretStr("wrong-response-value"),
    )

    clock = MutableClock()
    expiry = AuthenticationManager(
        verifier,
        clock=clock,
        challenge_ttl=timedelta(seconds=1),
        event_sink=sink,
    )
    expired_issue = expiry.issue_challenge(binding)
    assert expired_issue.challenge is not None
    expired_response = answer_challenge(expired_issue.challenge, verifier)
    raw_values.extend(
        [
            expired_issue.challenge.challenge_id.get_secret_value(),
            expired_issue.challenge.nonce.get_secret_value(),
            expired_response.get_secret_value(),
        ]
    )
    clock.value += timedelta(seconds=1)
    expiry.complete_challenge(expired_issue.challenge, expired_response)

    revoked = AuthenticationManager(verifier, event_sink=sink)
    revoked.revoke()

    raw = audit_path.read_text(encoding="utf-8")
    events = load_audit_events(audit_path)
    event_types = {
        event.metadata["session_authentication"]["event_type"] for event in events
    }
    assert {
        "authentication_success",
        "authentication_failure",
        "authentication_expiry",
        "authentication_revocation",
        "authentication_replay",
    } <= event_types
    for raw_value in raw_values:
        assert raw_value not in raw
    assert all(event.tool == "session_auth" for event in events)
    assert all(event.action_id is None for event in events)
    assert all(
        event.metadata["session_authentication"]["binding"] is None
        or event.metadata["session_authentication"]["binding"]["principal_ref"]
        == principal.audit_ref
        for event in events
    )
