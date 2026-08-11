"""Unit tests for structured audit logging (v0.8)."""

from __future__ import annotations

import json
from pathlib import Path

from council_agent.sandbox.config import audit_dir, init_sandbox
from council_agent.security import (
    TRUNCATION_MARKER,
    AuditLogger,
    default_audit_events_path,
    export_audit_events,
    filter_audit_events,
    get_audit_logger,
    load_audit_events,
    record_audit_event,
    set_audit_logger,
    truncate_value,
)


def test_record_audit_event_noop_without_logger() -> None:
    assert get_audit_logger() is None
    assert (
        record_audit_event("read_file", {"path": "a.txt"}, success=True) is None
    )


def test_audit_logger_appends_jsonl(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    logger = AuditLogger(path, session_id="sess-1")

    first = logger.record(
        "write_file",
        {"path": "a.txt", "content": "hi"},
        success=True,
        metadata={"bytes_written": 2},
    )
    second = logger.record(
        "run_command",
        {"command": "echo hi"},
        success=False,
        error="denied",
        metadata={"confirmation": "refused"},
    )

    assert first.session_id == "sess-1"
    assert second.success is False

    lines = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(lines) == 2
    assert lines[0]["tool"] == "write_file"
    assert lines[0]["args"]["path"] == "a.txt"
    assert lines[0]["success"] is True
    assert lines[0]["session_id"] == "sess-1"
    assert lines[0]["timestamp"]
    assert lines[1]["error"] == "denied"

    loaded = load_audit_events(path)
    assert len(loaded) == 2
    assert loaded[0].tool == "write_file"


def test_prior_events_remain_intact(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    logger = AuditLogger(path)
    logger.record("list_dir", {"path": "."}, success=True)
    before = path.read_text(encoding="utf-8")
    logger.record("read_file", {"path": "a.txt"}, success=True)
    after = path.read_text(encoding="utf-8")
    assert after.startswith(before)
    assert len(load_audit_events(path)) == 2


def test_truncate_value_marks_long_strings() -> None:
    long = "x" * 100
    truncated = truncate_value(long, max_chars=20)
    assert isinstance(truncated, str)
    assert truncated.endswith(TRUNCATION_MARKER)
    assert len(truncated) <= 20


def test_large_string_arg_truncated_in_audit_only(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    logger = AuditLogger(path, arg_max_chars=32)
    content = "y" * 200
    logger.record("write_file", {"path": "big.txt", "content": content}, success=True)

    stored = load_audit_events(path)[0]
    assert stored.args["content"].endswith(TRUNCATION_MARKER)
    assert len(stored.args["content"]) <= 32
    assert content == "y" * 200  # original unchanged


def test_record_audit_event_via_contextvar(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    logger = AuditLogger(path, session_id="ctx")
    token = set_audit_logger(logger)
    try:
        record = record_audit_event(
            "delete_file",
            {"path": "gone.txt"},
            success=True,
            metadata={"deleted": True},
        )
    finally:
        from council_agent.security import reset_audit_logger

        reset_audit_logger(token)

    assert record is not None
    assert record.session_id == "ctx"
    assert get_audit_logger() is None
    assert len(load_audit_events(path)) == 1


def test_init_sandbox_creates_audit_dir(tmp_path: Path) -> None:
    init_sandbox(tmp_path)
    assert audit_dir(tmp_path).is_dir()
    assert default_audit_events_path(tmp_path).parent == audit_dir(tmp_path)


def test_reinit_preserves_audit_events(tmp_path: Path) -> None:
    init_sandbox(tmp_path)
    events_path = default_audit_events_path(tmp_path)
    logger = AuditLogger(events_path, session_id="keep")
    logger.record("read_file", {"path": "x"}, success=True)
    before = events_path.read_text(encoding="utf-8")

    init_sandbox(tmp_path)
    assert events_path.read_text(encoding="utf-8") == before
    assert audit_dir(tmp_path).is_dir()


def test_filter_and_export(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    logger = AuditLogger(path)
    logger.record("a", {}, success=True, session_id="s1")
    logger.record("b", {}, success=True, session_id="s2")
    logger.record("c", {}, success=True, session_id="s1")

    events = load_audit_events(path)
    filtered = filter_audit_events(events, session_id="s1")
    assert [e.tool for e in filtered] == ["a", "c"]

    out = tmp_path / "out" / "export.jsonl"
    export_audit_events(filtered, out)
    exported = load_audit_events(out)
    assert len(exported) == 2
    assert all(e.session_id == "s1" for e in exported)
