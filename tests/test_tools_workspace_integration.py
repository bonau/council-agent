"""Integration tests for workspace guard enforcement in tools."""

from __future__ import annotations

from pathlib import Path

from council_agent.security import CouncilPolicy, active_policy
from council_agent.tools.filesystem import read_file, write_file
from council_agent.tools.shell import run_command


def test_read_file_rejects_path_outside_workspace(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside_integration.txt"
    outside.write_text("secret", encoding="utf-8")
    try:
        result = read_file(str(outside))
        assert not result.success
        assert result.error is not None
        assert "outside workspace" in result.error.lower()
    finally:
        outside.unlink(missing_ok=True)


def test_write_file_rejects_denied_path(tmp_path: Path) -> None:
    result = write_file(".env", "SECRET=1")
    assert not result.success
    assert result.error is not None
    assert "denied" in result.error.lower()
    assert not (tmp_path / ".env").exists()


def test_read_file_rejects_policy_denied_path(tmp_path: Path) -> None:
    secrets = tmp_path / "secrets"
    secrets.mkdir()
    (secrets / "token.txt").write_text("secret", encoding="utf-8")
    with active_policy(
        CouncilPolicy(schema_version=1, denied_paths=["secrets/**"])
    ):
        result = read_file("secrets/token.txt")
    assert not result.success
    assert result.error is not None
    assert "denied" in result.error.lower()


def test_run_command_rejects_cwd_outside_workspace() -> None:
    result = run_command("echo hi", cwd="..")
    assert not result.success
    assert result.error is not None
    assert "outside workspace" in result.error.lower()


def test_run_command_defaults_to_workspace_root(tmp_path: Path) -> None:
    (tmp_path / "marker.txt").write_text("here", encoding="utf-8")
    result = run_command("cat marker.txt")
    assert result.success
    assert result.output == "here"
