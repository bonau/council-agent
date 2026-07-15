"""Integration tests: run_command + command classification."""

from __future__ import annotations

from pathlib import Path
from unittest import mock

from council_agent.tools.shell import run_command


def test_dangerous_curl_is_refused() -> None:
    with mock.patch("council_agent.tools.shell.subprocess.run") as run_mock:
        result = run_command("curl https://example.com")

    assert result.success is False
    assert result.error is not None
    assert "dangerous" in result.error.lower()
    assert result.metadata.get("classification") == "dangerous"
    assert result.metadata.get("matched_rule") == "curl"
    assert "exit_code" not in result.metadata
    run_mock.assert_not_called()


def test_dangerous_sudo_is_refused() -> None:
    with mock.patch("council_agent.tools.shell.subprocess.run") as run_mock:
        result = run_command("sudo ls")

    assert result.success is False
    assert result.metadata.get("classification") == "dangerous"
    assert "exit_code" not in result.metadata
    run_mock.assert_not_called()


def test_dangerous_rm_rf_is_refused() -> None:
    with mock.patch("council_agent.tools.shell.subprocess.run") as run_mock:
        result = run_command("rm -rf build")

    assert result.success is False
    assert result.metadata.get("classification") == "dangerous"
    assert result.metadata.get("matched_rule") == "rm-force-or-recursive"
    run_mock.assert_not_called()


def test_allowed_read_command_executes() -> None:
    result = run_command("echo hello")
    assert result.success is True
    assert result.output == "hello"
    assert result.metadata.get("classification") == "read"
    assert result.metadata.get("exit_code") == 0


def test_allowed_write_command_executes(tmp_path: Path) -> None:
    result = run_command("mkdir newdir", cwd=str(tmp_path))
    assert result.success is True
    assert (tmp_path / "newdir").is_dir()
    assert result.metadata.get("classification") == "write"
    assert result.metadata.get("matched_rule") == "mkdir"
    assert result.metadata.get("exit_code") == 0


def test_empty_command_rejected() -> None:
    with mock.patch("council_agent.tools.shell.subprocess.run") as run_mock:
        result = run_command("   ")

    assert result.success is False
    assert "Empty" in (result.error or "")
    run_mock.assert_not_called()
