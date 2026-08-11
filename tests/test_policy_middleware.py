"""Unit tests for the mandatory policy middleware core."""

from __future__ import annotations

import contextvars
import json
from dataclasses import replace
from pathlib import Path

import pytest

from council_agent.sandbox.session import SessionManager, SessionMeta
from council_agent.security import CouncilPolicy, active_policy
from council_agent.security.audit import AuditLogger, load_audit_events
from council_agent.security.redaction import REDACTION_MARKER
from council_agent.security.middleware import (
    POLICY_VERSION_BUILTIN,
    POLICY_VERSION_PROJECT_V1,
    POLICY_VERSION_UNVERSIONED,
    SecurityContext,
    SecurityContextError,
    _TOOL_HANDLERS,
    get_security_context,
    invoke,
    security_context,
    without_security_context,
)
from council_agent.tools.base import ToolResult
from council_agent.tools.tracker import ToolCallTracker


@pytest.fixture(autouse=True)
def no_default_security_context(workspace_root: Path) -> None:
    with without_security_context():
        yield


def _success_handler(
    _context: SecurityContext,
    *,
    value: str = "ok",
) -> ToolResult:
    return ToolResult(success=True, output=value, metadata={"source": "handler"})


@pytest.fixture
def registered_read_handler(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(_TOOL_HANDLERS, "read_file", _success_handler)


def test_missing_context_fails_closed_without_calling_handler(
    registered_read_handler: None,
) -> None:
    result = invoke("read_file", value="blocked")

    assert result.success is False
    assert result.metadata["rejection_reason"] == "security_context_missing"
    assert result.metadata["decision"] == "deny"


def test_context_tracks_and_correlates_success(
    tmp_path: Path,
    registered_read_handler: None,
) -> None:
    tracker = ToolCallTracker(max_tool_calls=2)
    context = SecurityContext.create(
        tmp_path,
        request_id="request-1",
        tracker=tracker,
    )

    with security_context(context):
        result = invoke("read_file", value="content")

    assert result.success is True
    assert result.output == "content"
    assert result.metadata["request_id"] == "request-1"
    assert result.metadata["action_id"]
    assert result.metadata["decision"] == "allow"
    assert len(tracker.summaries) == 1
    assert tracker.summaries[0].metadata["action_id"] == result.metadata["action_id"]
    assert get_security_context() is None


def test_context_cleanup_and_copied_context_fail_closed(
    tmp_path: Path,
    registered_read_handler: None,
) -> None:
    context = SecurityContext.create(tmp_path)

    with security_context(context):
        copied = contextvars.copy_context()
        assert invoke("read_file").success is True

    after_cleanup = invoke("read_file")
    stale_copy = copied.run(invoke, "read_file")

    assert after_cleanup.metadata["rejection_reason"] == "security_context_missing"
    assert stale_copy.metadata["rejection_reason"] == "security_context_closed"


def test_closed_context_cannot_be_reinstalled(tmp_path: Path) -> None:
    context = SecurityContext.create(tmp_path)
    with security_context(context):
        pass

    with pytest.raises(SecurityContextError, match="closed"):
        with security_context(context):
            pass


def test_session_workspace_mismatch_is_rejected(tmp_path: Path) -> None:
    other = tmp_path / "other"
    other.mkdir()
    session = SessionManager(
        tmp_path / "session",
        SessionMeta(
            session_id="session-1",
            prompt="p",
            preset="test",
            workspace_root=str(other),
            started_at="2026-08-11T00:00:00+00:00",
        ),
    )

    with pytest.raises(SecurityContextError, match="workspace"):
        SecurityContext.create(tmp_path, session=session)


def test_audit_session_mismatch_is_rejected(tmp_path: Path) -> None:
    logger = AuditLogger(tmp_path / "events.jsonl", session_id="audit-session")

    with pytest.raises(SecurityContextError, match="audit identity"):
        SecurityContext.create(
            tmp_path,
            session_id="context-session",
            audit_logger=logger,
        )


def test_context_derives_policy_version_from_snapshot(tmp_path: Path) -> None:
    builtin = SecurityContext.create(tmp_path)
    project = SecurityContext.create(
        tmp_path,
        policy=CouncilPolicy(
            schema_version=1,
            denied_commands=["curl *"],
        ),
    )

    assert builtin.policy_version == POLICY_VERSION_BUILTIN
    assert project.policy_version == POLICY_VERSION_PROJECT_V1


def test_context_rejects_mismatched_policy_version(tmp_path: Path) -> None:
    context = replace(
        SecurityContext.create(tmp_path),
        policy_version=POLICY_VERSION_UNVERSIONED,
    )

    with pytest.raises(SecurityContextError, match="does not match"):
        context.validate(require_active=False)


def test_legacy_policy_view_updates_snapshot_version(tmp_path: Path) -> None:
    context = SecurityContext.create(tmp_path)
    policy = CouncilPolicy(schema_version=1, denied_paths=["secrets/**"])

    with security_context(context):
        assert get_security_context() is not None
        assert get_security_context().policy_version == POLICY_VERSION_BUILTIN
        with active_policy(policy):
            assert get_security_context() is not None
            assert (
                get_security_context().policy_version
                == POLICY_VERSION_PROJECT_V1
            )
        assert get_security_context() is not None
        assert get_security_context().policy_version == POLICY_VERSION_BUILTIN


def test_unknown_tool_is_denied_and_audited(tmp_path: Path) -> None:
    audit_path = tmp_path / "audit" / "events.jsonl"
    logger = AuditLogger(audit_path)
    context = SecurityContext.create(
        tmp_path,
        request_id="request-unknown",
        audit_logger=logger,
    )

    with security_context(context):
        result = invoke("not_registered", value="x")

    assert result.success is False
    assert result.metadata["rejection_reason"] == "unknown_tool"
    events = load_audit_events(audit_path)
    assert [event.phase for event in events] == ["attempt", "result"]
    assert events[0].action_id == events[1].action_id
    assert events[1].attempt_event_id == events[0].event_id
    assert events[1].decision == "deny"


def test_limit_denial_does_not_call_or_track_handler(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def handler(_context: SecurityContext, **_kwargs: object) -> ToolResult:
        calls.append("called")
        return ToolResult(success=True, output="unexpected")

    monkeypatch.setitem(_TOOL_HANDLERS, "read_file", handler)
    audit_path = tmp_path / "events.jsonl"
    tracker = ToolCallTracker(max_tool_calls=0)
    context = SecurityContext.create(
        tmp_path,
        tracker=tracker,
        audit_logger=AuditLogger(audit_path),
    )

    with security_context(context):
        result = invoke("read_file", path="blocked")

    assert result.success is False
    assert result.metadata["rejection_reason"] == "tool_limit"
    assert calls == []
    assert tracker.summaries == []
    assert tracker.limit_reached is True
    events = load_audit_events(audit_path)
    assert [event.phase for event in events] == ["attempt", "result"]
    assert events[0].action_id == events[1].action_id
    assert events[1].attempt_event_id == events[0].event_id
    assert events[1].decision == "deny"


def test_success_emits_correlated_attempt_and_result(
    tmp_path: Path,
    registered_read_handler: None,
) -> None:
    audit_path = tmp_path / "events.jsonl"
    context = SecurityContext.create(
        tmp_path,
        request_id="request-audit",
        audit_logger=AuditLogger(audit_path),
    )

    with security_context(context):
        result = invoke("read_file", value="audited")

    events = load_audit_events(audit_path)
    assert len(events) == 2
    attempt, completed = events
    assert attempt.phase == "attempt"
    assert attempt.success is None
    assert completed.phase == "result"
    assert completed.success is True
    assert completed.decision == "allow"
    assert attempt.request_id == completed.request_id == "request-audit"
    assert attempt.action_id == completed.action_id == result.metadata["action_id"]
    assert completed.attempt_event_id == attempt.event_id


def test_legacy_audit_line_loads_with_result_defaults(tmp_path: Path) -> None:
    audit_path = tmp_path / "legacy.jsonl"
    audit_path.write_text(
        json.dumps(
            {
                "timestamp": "2026-08-11T00:00:00+00:00",
                "tool": "read_file",
                "args": {"path": "a.txt"},
                "success": True,
                "metadata": {},
            }
        )
        + "\n",
        encoding="utf-8",
    )

    event = load_audit_events(audit_path)[0]
    assert event.phase == "result"
    assert event.success is True
    assert event.request_id is None
    assert event.action_id is None
    assert event.decision is None


def test_handler_exception_becomes_tracked_audited_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def broken(_context: SecurityContext, **_kwargs: object) -> ToolResult:
        raise RuntimeError("boom")

    monkeypatch.setitem(_TOOL_HANDLERS, "read_file", broken)
    audit_path = tmp_path / "events.jsonl"
    tracker = ToolCallTracker(max_tool_calls=1)
    context = SecurityContext.create(
        tmp_path,
        tracker=tracker,
        audit_logger=AuditLogger(audit_path),
    )

    with security_context(context):
        result = invoke("read_file")

    assert result.success is False
    assert result.metadata["rejection_reason"] == "tool_exception"
    assert result.metadata["decision"] == "deny"
    assert len(tracker.summaries) == 1
    events = load_audit_events(audit_path)
    assert events[-1].phase == "result"
    assert events[-1].success is False
    assert events[-1].decision == "deny"


def test_session_receives_one_correlated_result(
    tmp_path: Path,
    registered_read_handler: None,
) -> None:
    session_dir = tmp_path / "session"
    session_dir.mkdir()
    session = SessionManager(
        session_dir,
        SessionMeta(
            session_id="session-1",
            prompt="p",
            preset="test",
            workspace_root=str(tmp_path),
            started_at="2026-08-11T00:00:00+00:00",
        ),
    )
    session.tools_path.write_text("", encoding="utf-8")
    context = SecurityContext.create(tmp_path, session=session)

    with security_context(context):
        result = invoke("read_file")

    assert result.success is True
    assert session.count_tool_lines() == 1
    assert session.meta.tool_call_count == 1
    line = json.loads(session.tools_path.read_text(encoding="utf-8"))
    assert line["request_id"] == result.metadata["request_id"]
    assert line["action_id"] == result.metadata["action_id"]


def test_session_links_exact_audit_events_and_redacts_all_result_fields(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "sk-or-v1-abcdefghijklmnopqrstuv"

    def handler(_context: SecurityContext, **_kwargs: object) -> ToolResult:
        return ToolResult(
            success=False,
            output=f"Authorization: Bearer {secret}",
            error=f"password={secret}",
            metadata={"access_token": secret},
        )

    monkeypatch.setitem(_TOOL_HANDLERS, "read_file", handler)
    session_dir = tmp_path / "session"
    session_dir.mkdir()
    session = SessionManager(
        session_dir,
        SessionMeta(
            session_id="session-1",
            prompt="p",
            preset="test",
            workspace_root=str(tmp_path),
            started_at="2026-08-11T00:00:00+00:00",
        ),
    )
    session.tools_path.write_text("", encoding="utf-8")
    audit_path = tmp_path / "audit" / "events.jsonl"
    context = SecurityContext.create(
        tmp_path,
        request_id="request-secret",
        session=session,
        audit_logger=AuditLogger(audit_path, session_id="session-1"),
    )

    with security_context(context):
        result = invoke("read_file", token=secret)

    events = load_audit_events(audit_path)
    session_text = session.tools_path.read_text(encoding="utf-8")
    session_line = json.loads(session_text)
    audit_text = audit_path.read_text(encoding="utf-8")
    assert result.success is False
    assert secret not in audit_text
    assert secret not in session_text
    assert REDACTION_MARKER in audit_text
    assert REDACTION_MARKER in session_text
    assert events[1].attempt_event_id == events[0].event_id
    assert session_line["request_id"] == "request-secret"
    assert session_line["action_id"] == result.metadata["action_id"]
    assert session_line["audit_attempt_event_id"] == events[0].event_id
    assert session_line["audit_result_event_id"] == events[1].event_id


def test_audit_attempt_failure_denies_before_handler_without_secret_echo(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called = False

    def handler(_context: SecurityContext, **_kwargs: object) -> ToolResult:
        nonlocal called
        called = True
        return ToolResult(success=True, output="unexpected")

    monkeypatch.setitem(_TOOL_HANDLERS, "read_file", handler)
    logger = AuditLogger(tmp_path / "audit" / "events.jsonl")
    monkeypatch.setattr(
        logger,
        "record",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            RuntimeError("api_key=must-not-echo")
        ),
    )
    context = SecurityContext.create(tmp_path, audit_logger=logger)

    with security_context(context):
        result = invoke("read_file", path="a.txt")

    assert result.success is False
    assert result.metadata["rejection_reason"] == "audit_failure"
    assert "must-not-echo" not in (result.error or "")
    assert called is False
