"""Dispatcher integration tests for normalized trust-decision evidence."""

from __future__ import annotations

import json
from pathlib import Path
from unittest import mock

from council_agent.sandbox.session import SessionManager, SessionMeta
from council_agent.security import (
    AuditLogger,
    ConfirmMode,
    ConfirmationPolicy,
    CouncilPolicy,
    Principal,
    PrincipalKind,
    PrincipalScope,
    SecurityContext,
    full_scope_principal,
    load_audit_events,
    pipeline_attempt,
    security_context,
    without_security_context,
)
from council_agent.tools import read_file, run_command, write_file


def _principal(*scopes: PrincipalScope) -> Principal:
    return Principal(
        principal_id="matrix-user",
        kind=PrincipalKind.LOCAL_USER,
        issuer="pytest",
        scopes=frozenset(scopes),
    )


def test_auto_is_only_interaction_after_scope_authority(tmp_path: Path) -> None:
    context = SecurityContext.create(
        tmp_path,
        principal=_principal(PrincipalScope.READ),
        confirmation=ConfirmationPolicy(mode=ConfirmMode.AUTO),
    )

    with without_security_context(), security_context(context):
        result = write_file("blocked.txt", "blocked")

    decision = result.metadata["trust_decision"]
    assert result.success is False
    assert result.metadata["rejection_reason"] == "scope_insufficient"
    assert result.metadata["decision"] == "deny"
    assert decision["outcome"] == "deny"
    assert decision["reason"] == "scope_insufficient"
    assert decision["vector"] == {
        "policy": "policy_allowed",
        "scope": "scope_insufficient",
        "authentication": "authentication_not_required",
        "grant": "trust_grant_not_required",
        "risk": "mutate",
        "interaction": "auto",
    }
    assert not (tmp_path / "blocked.txt").exists()


def test_policy_wins_simultaneous_scope_denial_without_process(
    tmp_path: Path,
) -> None:
    context = SecurityContext.create(
        tmp_path,
        principal=_principal(PrincipalScope.READ),
        policy=CouncilPolicy(
            schema_version=1,
            denied_commands=["mkdir *"],
        ),
        confirmation=ConfirmationPolicy(mode=ConfirmMode.AUTO),
    )

    with (
        without_security_context(),
        security_context(context),
        mock.patch("council_agent.tools.shell.subprocess.run") as process,
    ):
        result = run_command("mkdir marker")

    decision = result.metadata["trust_decision"]
    assert result.metadata["rejection_reason"] == "policy_denied"
    assert result.metadata["scope_authorization"]["reason"] == "scope_insufficient"
    assert decision["outcome"] == "deny"
    assert decision["reason"] == "policy_denied"
    assert decision["vector"]["scope"] == "scope_insufficient"
    assert decision["vector"]["interaction"] == "auto"
    assert process.call_count == 0
    assert not (tmp_path / "marker").exists()


def test_auto_cannot_replace_required_authentication(tmp_path: Path) -> None:
    marker = tmp_path / "marker"
    marker.mkdir()
    context = SecurityContext.create(
        tmp_path,
        principal=full_scope_principal("matrix-auth-user", issuer="pytest"),
        require_high_risk_step_up=True,
        confirmation=ConfirmationPolicy(mode=ConfirmMode.AUTO),
    )

    with (
        without_security_context(),
        security_context(context),
        mock.patch("council_agent.tools.shell.subprocess.run") as process,
    ):
        result = run_command("rm -rf marker")

    decision = result.metadata["trust_decision"]
    assert result.metadata["rejection_reason"] == "authentication_missing"
    assert decision["outcome"] == "deny"
    assert decision["reason"] == "authentication_missing"
    assert decision["vector"]["authentication"] == "authentication_missing"
    assert decision["vector"]["interaction"] == "auto"
    assert process.call_count == 0
    assert marker.is_dir()


def test_refused_interaction_is_final_gate_for_authorized_mutation(
    tmp_path: Path,
) -> None:
    context = SecurityContext.create(
        tmp_path,
        principal=full_scope_principal("matrix-refuse-user", issuer="pytest"),
        confirmation=ConfirmationPolicy(mode=ConfirmMode.REFUSE),
    )

    with without_security_context(), security_context(context):
        result = write_file("blocked.txt", "blocked")

    decision = result.metadata["trust_decision"]
    assert result.metadata["confirmation"] == "refused"
    assert result.metadata["rejection_reason"] == "confirmation_refused"
    assert decision["outcome"] == "deny"
    assert decision["reason"] == "confirmation_refused"
    assert decision["vector"]["scope"] == "scope_allowed"
    assert decision["vector"]["grant"] == "trust_grant_not_required"
    assert not (tmp_path / "blocked.txt").exists()


def test_ordinary_operation_failure_remains_security_allowed(
    tmp_path: Path,
) -> None:
    context = SecurityContext.create(
        tmp_path,
        principal=_principal(PrincipalScope.READ),
        confirmation=ConfirmationPolicy(mode=ConfirmMode.REFUSE),
    )

    with without_security_context(), security_context(context):
        result = read_file("missing.txt")

    decision = result.metadata["trust_decision"]
    assert result.success is False
    assert "rejection_reason" not in result.metadata
    assert result.metadata["decision"] == "allow"
    assert decision["outcome"] == "allow"
    assert decision["reason"] == "decision_allowed"
    assert decision["vector"]["interaction"] == "not_required"


def test_runtime_grant_state_is_explicitly_disconnected(
    tmp_path: Path,
) -> None:
    (tmp_path / "item.txt").write_text("content", encoding="utf-8")
    context = SecurityContext.create(
        tmp_path,
        principal=_principal(PrincipalScope.READ),
    )

    with (
        without_security_context(),
        security_context(context),
        mock.patch(
            "council_agent.security.trust_grants.TrustGrantStore.lookup"
        ) as lookup,
    ):
        result = read_file("item.txt")

    assert result.success is True
    assert (
        result.metadata["trust_decision"]["vector"]["grant"]
        == "trust_grant_not_required"
    )
    assert lookup.call_count == 0


def test_result_tracker_session_and_audit_share_matrix_evidence(
    tmp_path: Path,
) -> None:
    session_dir = tmp_path / "session"
    session_dir.mkdir()
    session = SessionManager(
        session_dir,
        SessionMeta(
            session_id="matrix-session",
            prompt="matrix evidence",
            preset="test",
            workspace_root=str(tmp_path),
            started_at="2026-08-11T00:00:00+00:00",
        ),
    )
    session.tools_path.write_text("", encoding="utf-8")
    audit_path = tmp_path / "audit" / "events.jsonl"
    context = SecurityContext.create(
        tmp_path,
        request_id="matrix-request",
        session_id="matrix-session",
        principal=full_scope_principal("matrix-evidence-user", issuer="pytest"),
        confirmation=ConfirmationPolicy(mode=ConfirmMode.AUTO),
        session=session,
        audit_logger=AuditLogger(audit_path, session_id="matrix-session"),
    )

    with without_security_context(), security_context(context):
        with pipeline_attempt("pipeline-attempt-1"):
            result = write_file("written.txt", "content")
        with pipeline_attempt("pipeline-attempt-2"):
            later_result = write_file("later.txt", "later")

    matrix = result.metadata["trust_decision"]
    tracker_matrix = context.tracker.summaries[0].metadata["trust_decision"]
    session_lines = [
        json.loads(line)
        for line in session.tools_path.read_text(encoding="utf-8").splitlines()
    ]
    session_matrix = session_lines[0]["metadata"]["trust_decision"]
    events = load_audit_events(audit_path)
    result_event = [
        event for event in events if event.phase == "result"
    ][0]

    assert matrix["outcome"] == "allow"
    assert matrix["reason"] == "decision_allowed"
    assert tracker_matrix == session_matrix == result_event.metadata["trust_decision"]
    assert tracker_matrix == matrix
    assert result.metadata["pipeline_attempt_id"] == "pipeline-attempt-1"
    assert later_result.metadata["pipeline_attempt_id"] == "pipeline-attempt-2"
    assert [
        summary.metadata["pipeline_attempt_id"]
        for summary in context.tracker.summaries
    ] == ["pipeline-attempt-1", "pipeline-attempt-2"]
    assert [line["pipeline_attempt_id"] for line in session_lines] == [
        "pipeline-attempt-1",
        "pipeline-attempt-2",
    ]
    assert [
        event.metadata["pipeline_attempt_id"] for event in events
    ] == [
        "pipeline-attempt-1",
        "pipeline-attempt-1",
        "pipeline-attempt-2",
        "pipeline-attempt-2",
    ]
    assert session_lines[0]["audit_attempt_event_id"]
    assert session_lines[0]["audit_result_event_id"]
