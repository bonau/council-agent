"""Unit tests for structured audit logging (v0.8)."""

from __future__ import annotations

import json
import multiprocessing
import os
from pathlib import Path

import pytest

from council_agent.sandbox.config import audit_dir, init_sandbox
from council_agent.security import (
    AUDIT_SCHEMA_VERSION,
    REDACTION_MARKER,
    TRUNCATION_MARKER,
    AuditLogger,
    AuditIntegrityError,
    AuditRecord,
    compute_audit_event_id,
    default_audit_events_path,
    export_audit_events,
    filter_audit_events,
    get_audit_logger,
    load_audit_events,
    load_audit_events_with_integrity,
    record_audit_event,
    sanitize_value,
    set_audit_logger,
    truncate_value,
    verify_audit_events,
)


def _append_audit_event_in_process(args: tuple[str, int]) -> int | None:
    path, index = args
    return AuditLogger(path).record(
        "process-writer",
        {"index": index},
        success=True,
    ).sequence


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
    exported = [
        json.loads(line)
        for line in out.read_text(encoding="utf-8").splitlines()
    ]
    assert len(exported) == 2
    assert all(event["session_id"] == "s1" for event in exported)
    assert [event["event_id"] for event in exported] == [
        filtered[0].event_id,
        filtered[1].event_id,
    ]


def test_recursive_redaction_precedes_truncation_and_preserves_ordinary_values() -> None:
    jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTYifQ.signature123"
    private_key = (
        "-----BEGIN PRIVATE KEY-----\nsecret-material\n-----END PRIVATE KEY-----"
    )
    payload = {
        "api_key": "short-secret",
        "nested": {
            "message": (
                "Authorization: Bearer abcdefghijklmnop "
                "token=plain-secret "
                f"jwt={jwt} key={private_key}"
            ),
            "count": 3,
            "path": "src/example.py",
        },
        "items": ["sk-or-v1-abcdefghijklmnop", "ordinary"],
    }

    sanitized = sanitize_value(payload, max_chars=512)

    assert sanitized["api_key"] == REDACTION_MARKER
    assert "short-secret" not in json.dumps(sanitized)
    assert "abcdefghijklmnop" not in json.dumps(sanitized)
    assert "plain-secret" not in json.dumps(sanitized)
    assert "secret-material" not in json.dumps(sanitized)
    assert jwt not in json.dumps(sanitized)
    assert sanitized["nested"]["count"] == 3
    assert sanitized["nested"]["path"] == "src/example.py"
    assert sanitized["items"][1] == "ordinary"


def test_large_secret_is_redacted_without_leaking_prefix(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    secret = "sk-" + ("a" * 200)
    logger = AuditLogger(path, arg_max_chars=32)

    logger.record(
        "write_file",
        {"content": secret},
        success=False,
        error=f"api_key={secret}",
    )

    stored = path.read_text(encoding="utf-8")
    assert secret not in stored
    assert secret[:20] not in stored
    assert REDACTION_MARKER in stored


def test_versioned_events_have_contiguous_sequence_and_stable_ids(
    tmp_path: Path,
) -> None:
    path = tmp_path / "events.jsonl"
    first_logger = AuditLogger(path, session_id="s1")
    second_logger = AuditLogger(path, session_id="s1")

    first = first_logger.record("admin-a", {}, success=True)
    second = second_logger.record("admin-b", {}, success=True)
    restarted = AuditLogger(path, session_id="s1").record(
        "admin-c",
        {},
        success=True,
    )
    loaded, report = load_audit_events_with_integrity(path)

    assert report.status == "verified"
    assert report.last_sequence == 3
    assert [event.sequence for event in loaded] == [1, 2, 3]
    assert [event.event_id for event in loaded] == [
        first.event_id,
        second.event_id,
        restarted.event_id,
    ]
    assert all(event.schema_version == AUDIT_SCHEMA_VERSION for event in loaded)
    assert all(event.event_id == compute_audit_event_id(event) for event in loaded)


@pytest.mark.skipif(os.name != "posix", reason="uses POSIX cross-process lock")
def test_process_writers_allocate_one_contiguous_sequence(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    AuditLogger(path)
    context = multiprocessing.get_context("spawn")

    with context.Pool(processes=4) as pool:
        sequences = pool.map(
            _append_audit_event_in_process,
            [(str(path), index) for index in range(12)],
        )

    events, report = load_audit_events_with_integrity(path)
    assert sorted(sequences) == list(range(1, 13))
    assert [event.sequence for event in events] == list(range(1, 13))
    assert report.status == "verified"


def test_attempt_result_exact_reference_is_verified(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    logger = AuditLogger(path, session_id="session-1")
    attempt = logger.record(
        "read_file",
        {"path": "a.txt"},
        success=None,
        phase="attempt",
        request_id="request-1",
        action_id="action-1",
    )
    result = logger.record(
        "read_file",
        {"path": "a.txt"},
        success=True,
        phase="result",
        request_id="request-1",
        action_id="action-1",
        decision="allow",
        attempt_event_id=attempt.event_id,
    )

    events, report = load_audit_events_with_integrity(path)
    assert report.status == "verified"
    assert result.attempt_event_id == attempt.event_id
    assert events[1].attempt_event_id == events[0].event_id


def _rewrite_lines(path: Path, lines: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(
            json.dumps(line, ensure_ascii=False, sort_keys=True) + "\n"
            for line in lines
        ),
        encoding="utf-8",
    )


def test_gap_duplicate_and_reorder_are_detected(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    logger = AuditLogger(path)
    logger.record("a", {}, success=True)
    logger.record("b", {}, success=True)
    logger.record("c", {}, success=True)
    original = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
    ]

    for name, changed in {
        "gap": [original[0], original[2]],
        "duplicate": [original[0], original[0], original[1]],
        "reorder": [original[1], original[0], original[2]],
    }.items():
        candidate = tmp_path / f"{name}.jsonl"
        _rewrite_lines(candidate, changed)
        with pytest.raises(AuditIntegrityError, match="sequence|event_id"):
            load_audit_events(candidate)


def test_content_mutation_is_detected_without_echoing_content(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    AuditLogger(path).record("read_file", {"path": "safe.txt"}, success=True)
    line = json.loads(path.read_text(encoding="utf-8"))
    line["args"]["path"] = "sensitive-mutated-value"
    _rewrite_lines(path, [line])

    with pytest.raises(AuditIntegrityError) as exc_info:
        load_audit_events(path)

    assert exc_info.value.reason == "event_id does not match canonical content"
    assert "sensitive-mutated-value" not in str(exc_info.value)


@pytest.mark.parametrize(
    "content",
    [
        '{"schema_version":1',
        '{"timestamp":"x"}',
        "\n",
    ],
)
def test_partial_malformed_and_blank_lines_are_detected(
    tmp_path: Path,
    content: str,
) -> None:
    path = tmp_path / "broken.jsonl"
    path.write_text(content, encoding="utf-8")

    with pytest.raises(AuditIntegrityError):
        load_audit_events(path)


def test_unterminated_complete_json_is_detected(tmp_path: Path) -> None:
    path = tmp_path / "unterminated.jsonl"
    path.write_text(
        json.dumps(
            {
                "timestamp": "2026-08-11T00:00:00+00:00",
                "tool": "legacy",
                "args": {},
                "success": True,
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(AuditIntegrityError, match="unterminated"):
        load_audit_events(path)


def test_dangling_attempt_and_mismatched_result_are_detected(tmp_path: Path) -> None:
    dangling_path = tmp_path / "dangling.jsonl"
    logger = AuditLogger(dangling_path)
    attempt = logger.record(
        "read_file",
        {},
        success=None,
        phase="attempt",
        request_id="r",
        action_id="a",
    )
    with pytest.raises(AuditIntegrityError, match="no result"):
        load_audit_events(dangling_path)

    mismatched = AuditRecord(
        timestamp="2026-08-11T00:00:01+00:00",
        tool="write_file",
        args={},
        success=False,
        phase="result",
        request_id="different",
        action_id="a",
        sequence=2,
        attempt_event_id=attempt.event_id,
    )
    mismatched.event_id = compute_audit_event_id(mismatched)

    with pytest.raises(AuditIntegrityError, match="does not match"):
        verify_audit_events([attempt, mismatched])


def test_legacy_events_are_sanitized_and_explicitly_unverified(
    tmp_path: Path,
) -> None:
    path = tmp_path / "legacy.jsonl"
    path.write_text(
        json.dumps(
            {
                "timestamp": "2026-08-11T00:00:00+00:00",
                "tool": "run_command",
                "args": {"token": "legacy-secret"},
                "success": False,
                "error": "Authorization: Bearer legacy-token-value",
                "metadata": {},
            }
        )
        + "\n",
        encoding="utf-8",
    )

    events, report = load_audit_events_with_integrity(path)

    assert report.status == "legacy_unverified"
    assert report.legacy_events == 1
    assert events[0].schema_version == 0
    assert events[0].args["token"] == REDACTION_MARKER
    assert "legacy-token-value" not in (events[0].error or "")


def test_empty_history_has_explicit_status(tmp_path: Path) -> None:
    events, report = load_audit_events_with_integrity(tmp_path / "missing.jsonl")
    assert events == []
    assert report.status == "empty"
