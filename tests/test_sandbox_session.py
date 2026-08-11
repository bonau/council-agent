"""Tests for SessionManager and `.council/config.yaml` loader."""

from __future__ import annotations

import json
import stat
from pathlib import Path

import pytest
import yaml

from council_agent.sandbox.config import (
    CouncilConfig,
    init_sandbox,
    is_sandbox_initialized,
    load_council_config,
    resolve_workspace_root,
    write_council_config,
)
from council_agent.sandbox.session import SessionManager
from council_agent.security import REDACTION_MARKER


def test_init_sandbox_creates_config(tmp_path: Path) -> None:
    config = init_sandbox(tmp_path)

    assert is_sandbox_initialized(tmp_path)
    assert config.workspace_root == str(tmp_path.resolve())
    assert (tmp_path / ".council" / "config.yaml").is_file()
    assert (tmp_path / ".council" / "sessions").is_dir()

    loaded = load_council_config(tmp_path)
    assert loaded.workspace_root == config.workspace_root
    assert loaded.denied_patterns == []


def test_init_sandbox_idempotent_preserves_sessions(tmp_path: Path) -> None:
    init_sandbox(tmp_path)
    session = SessionManager.create(
        prompt="keep me",
        preset="glm-stack",
        workspace_root=tmp_path,
        project_root=tmp_path,
    )
    session_dir = session.session_dir

    again = init_sandbox(tmp_path)
    assert again.workspace_root == str(tmp_path.resolve())
    assert session_dir.is_dir()
    assert (session_dir / "meta.json").is_file()


def test_config_loader_supports_denied_patterns(tmp_path: Path) -> None:
    write_council_config(
        tmp_path,
        CouncilConfig(
            workspace_root=str(tmp_path),
            denied_patterns=["secrets/**"],
        ),
    )
    loaded = load_council_config(tmp_path)
    assert loaded.denied_patterns == ["secrets/**"]
    raw = yaml.safe_load((tmp_path / ".council" / "config.yaml").read_text())
    assert raw["denied_patterns"] == ["secrets/**"]


def test_session_create_append_finalize(tmp_path: Path) -> None:
    init_sandbox(tmp_path)
    session = SessionManager.create(
        prompt="do work",
        preset="glm-stack",
        workspace_root=tmp_path,
        project_root=tmp_path,
    )

    meta = json.loads(session.meta_path.read_text(encoding="utf-8"))
    assert meta["prompt"] == "do work"
    assert meta["preset"] == "glm-stack"
    assert meta["workspace_root"] == str(tmp_path.resolve())
    assert meta["started_at"]
    assert meta["ended_at"] is None
    assert meta["tool_call_count"] == 0
    assert session.tools_path.is_file()

    session.append_tool_call(
        "write_file",
        {"path": "a.txt", "content": "hi"},
        success=True,
        metadata={"bytes_written": 2},
        output="hi",
    )
    session.append_tool_call(
        "read_file",
        {"path": "a.txt"},
        success=False,
        error="boom",
    )

    lines = [
        json.loads(line)
        for line in session.tools_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(lines) == 2
    assert lines[0]["tool"] == "write_file"
    assert lines[0]["args"]["path"] == "a.txt"
    assert lines[0]["success"] is True
    assert lines[0]["timestamp"]
    assert lines[1]["success"] is False
    assert lines[1]["error"] == "boom"

    session.finalize(status="completed")
    meta = json.loads(session.meta_path.read_text(encoding="utf-8"))
    assert meta["ended_at"]
    assert meta["status"] == "completed"
    assert meta["tool_call_count"] == 2


def test_session_persistence_redacts_and_retains_audit_linkage(
    tmp_path: Path,
) -> None:
    init_sandbox(tmp_path)
    secret = "sk-or-v1-abcdefghijklmnopqrstuv"
    session = SessionManager.create(
        prompt=f"Use api_key={secret}",
        preset="glm-stack",
        workspace_root=tmp_path,
        project_root=tmp_path,
    )
    session.append_tool_call(
        "run_command",
        {"command": f"echo Bearer {secret}", "token": secret},
        success=False,
        metadata={"nested": {"access_token": secret}},
        output=f"Authorization: Bearer {secret}",
        error=f"password={secret}",
        request_id="request-1",
        action_id="action-1",
        audit_attempt_event_id="sha256:attempt",
        audit_result_event_id="sha256:result",
    )

    meta_text = session.meta_path.read_text(encoding="utf-8")
    tools_text = session.tools_path.read_text(encoding="utf-8")
    assert secret not in meta_text
    assert secret not in tools_text
    assert REDACTION_MARKER in meta_text
    record = json.loads(tools_text)
    assert record["args"]["token"] == REDACTION_MARKER
    assert record["metadata"]["nested"]["access_token"] == REDACTION_MARKER
    assert record["request_id"] == "request-1"
    assert record["action_id"] == "action-1"
    assert record["audit_attempt_event_id"] == "sha256:attempt"
    assert record["audit_result_event_id"] == "sha256:result"


@pytest.mark.skipif(not hasattr(stat, "S_IMODE"), reason="POSIX mode unavailable")
def test_control_plane_permissions_are_owner_only(tmp_path: Path) -> None:
    init_sandbox(tmp_path)
    session = SessionManager.create(
        prompt="work",
        preset="glm-stack",
        workspace_root=tmp_path,
        project_root=tmp_path,
    )

    directories = [
        tmp_path / ".council",
        tmp_path / ".council" / "audit",
        tmp_path / ".council" / "sessions",
        session.session_dir,
    ]
    files = [
        tmp_path / ".council" / "config.yaml",
        session.meta_path,
        session.tools_path,
    ]
    assert all(stat.S_IMODE(path.stat().st_mode) == 0o700 for path in directories)
    assert all(stat.S_IMODE(path.stat().st_mode) == 0o600 for path in files)


def test_loading_legacy_session_metadata_redacts_prompt(tmp_path: Path) -> None:
    session_dir = tmp_path / "legacy"
    session_dir.mkdir()
    secret = "sk-or-v1-abcdefghijklmnopqrstuv"
    (session_dir / "meta.json").write_text(
        json.dumps(
            {
                "session_id": "legacy",
                "prompt": f"api_key={secret}",
                "preset": "glm-stack",
                "workspace_root": str(tmp_path),
                "started_at": "2026-08-11T00:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )

    loaded = SessionManager.load(session_dir)
    assert secret not in loaded.meta.prompt
    assert REDACTION_MARKER in loaded.meta.prompt


def test_session_create_requires_initialized_sandbox(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="Sandbox not initialized"):
        SessionManager.create(
            prompt="x",
            preset="glm-stack",
            workspace_root=tmp_path,
            project_root=tmp_path,
        )


def test_latest_session(tmp_path: Path) -> None:
    init_sandbox(tmp_path)
    first = SessionManager.create(
        prompt="first",
        preset="glm-stack",
        workspace_root=tmp_path,
        project_root=tmp_path,
    )
    second = SessionManager.create(
        prompt="second",
        preset="glm-stack",
        workspace_root=tmp_path,
        project_root=tmp_path,
    )
    latest = SessionManager.latest(tmp_path)
    assert latest is not None
    assert latest.meta.session_id == second.meta.session_id
    assert first.meta.session_id != second.meta.session_id


def test_resolve_workspace_root_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "project"
    other = tmp_path / "other"
    project.mkdir()
    other.mkdir()

    monkeypatch.delenv("COUNCIL_WORKSPACE_ROOT", raising=False)
    monkeypatch.chdir(project)

    assert resolve_workspace_root(search_from=project) == project.resolve()

    monkeypatch.setenv("COUNCIL_WORKSPACE_ROOT", str(other))
    assert resolve_workspace_root(search_from=project) == other.resolve()

    init_sandbox(project)
    assert resolve_workspace_root(search_from=project) == project.resolve()

    cli = tmp_path / "cli-root"
    cli.mkdir()
    assert resolve_workspace_root(cli, search_from=project) == cli.resolve()
