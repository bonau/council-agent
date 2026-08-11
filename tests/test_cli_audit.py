"""CLI tests for council audit show / export."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from council_agent.cli import app
from council_agent.sandbox.config import init_sandbox
from council_agent.security import (
    REDACTION_MARKER,
    AuditLogger,
    default_audit_events_path,
)

runner = CliRunner()


def _seed_events(project: Path) -> None:
    init_sandbox(project)
    logger = AuditLogger(default_audit_events_path(project))
    logger.record("write_file", {"path": "a.txt"}, success=True, session_id="s1")
    logger.record("run_command", {"command": "echo"}, success=False, error="no", session_id="s2")
    logger.record("list_dir", {"path": "."}, success=True, session_id="s1")


def test_audit_show_empty(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["audit", "show"])
    assert result.exit_code == 0, result.output
    assert "No audit events" in result.output
    assert "Integrity: empty" in result.output


def test_audit_show_populated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _seed_events(tmp_path)
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["audit", "show"])
    assert result.exit_code == 0, result.output
    assert "write_file" in result.output
    assert "run_command" in result.output
    assert "list_dir" in result.output
    assert "s1" in result.output
    assert "integrity=verified" in result.output


def test_audit_show_session_filter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed_events(tmp_path)
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["audit", "show", "--session", "s2"])
    assert result.exit_code == 0, result.output
    assert "run_command" in result.output
    assert "write_file" not in result.output


def test_audit_show_with_workspace_flag(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    project.mkdir()
    _seed_events(project)
    result = runner.invoke(app, ["audit", "show", "--workspace", str(project)])
    assert result.exit_code == 0, result.output
    assert "write_file" in result.output


def test_audit_export_all_jsonl(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed_events(tmp_path)
    monkeypatch.chdir(tmp_path)
    out = tmp_path / "out.jsonl"
    result = runner.invoke(app, ["audit", "export", str(out)])
    assert result.exit_code == 0, result.output
    assert out.is_file()
    lines = [json.loads(line) for line in out.read_text().splitlines() if line.strip()]
    assert len(lines) == 3
    assert lines[0]["tool"] == "write_file"
    assert lines[0]["event_id"].startswith("sha256:")
    assert "Integrity:" in result.output
    assert "verified" in result.output


def test_audit_export_filtered_by_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed_events(tmp_path)
    monkeypatch.chdir(tmp_path)
    out = tmp_path / "s1.jsonl"
    result = runner.invoke(
        app, ["audit", "export", str(out), "--session", "s1"]
    )
    assert result.exit_code == 0, result.output
    lines = [json.loads(line) for line in out.read_text().splitlines() if line.strip()]
    assert len(lines) == 2
    assert all(line["session_id"] == "s1" for line in lines)


def test_audit_export_invalid_format(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(
        app, ["audit", "export", str(tmp_path / "x.jsonl"), "--format", "csv"]
    )
    assert result.exit_code == 1
    assert "Invalid" in result.output


def test_legacy_show_and_export_are_sanitized_and_unverified(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    init_sandbox(tmp_path)
    secret = "sk-or-v1-abcdefghijklmnopqrstuv"
    events_path = default_audit_events_path(tmp_path)
    events_path.write_text(
        json.dumps(
            {
                "timestamp": "2026-08-11T00:00:00+00:00",
                "tool": "run_command",
                "args": {"api_key": secret},
                "success": False,
                "error": f"Authorization: Bearer {secret}",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    shown = runner.invoke(app, ["audit", "show"])
    out = tmp_path / "legacy-export.jsonl"
    exported = runner.invoke(app, ["audit", "export", str(out)])

    assert shown.exit_code == 0, shown.output
    assert "legacy_unverified" in shown.output
    assert secret not in shown.output
    assert exported.exit_code == 0, exported.output
    assert "legacy_unverified" in exported.output
    exported_text = out.read_text(encoding="utf-8")
    assert secret not in exported_text
    assert REDACTION_MARKER in exported_text


def test_invalid_audit_history_fails_show_and_export_without_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _seed_events(tmp_path)
    events_path = default_audit_events_path(tmp_path)
    lines = events_path.read_text(encoding="utf-8").splitlines()
    events_path.write_text("\n".join([lines[0], lines[2]]) + "\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    shown = runner.invoke(app, ["audit", "show"])
    out = tmp_path / "must-not-exist.jsonl"
    exported = runner.invoke(app, ["audit", "export", str(out)])

    assert shown.exit_code == 1
    assert "Audit Integrity Error" in shown.output
    assert "expected sequence" in shown.output
    assert exported.exit_code == 1
    assert "Audit Integrity Error" in exported.output
    assert not out.exists()
