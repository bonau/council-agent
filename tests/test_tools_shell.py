"""Tests for shell tools."""

import subprocess
from pathlib import Path
from unittest import mock

from council_agent.tools.shell import run_command


def test_run_command_success() -> None:
    result = run_command("echo hello")
    assert result.success
    assert result.output == "hello"
    assert result.metadata["exit_code"] == 0
    assert "duration_ms" in result.metadata


def test_run_command_failure() -> None:
    completed = subprocess.CompletedProcess(
        args=[],
        returncode=42,
        stdout="",
        stderr="failed",
    )
    with mock.patch(
        "council_agent.tools.shell.subprocess.run",
        return_value=completed,
    ):
        result = run_command("echo hello")
    assert not result.success
    assert result.metadata["exit_code"] == 42
    assert result.error == "failed"


def test_run_command_stderr() -> None:
    completed = subprocess.CompletedProcess(
        args=[],
        returncode=1,
        stdout="",
        stderr="err",
    )
    with mock.patch(
        "council_agent.tools.shell.subprocess.run",
        return_value=completed,
    ):
        result = run_command("echo hello")
    assert not result.success
    assert result.error == "err"
    assert result.metadata["exit_code"] == 1


def test_run_command_with_cwd(tmp_path: Path) -> None:
    (tmp_path / "marker.txt").write_text("here", encoding="utf-8")
    result = run_command("cat marker.txt", cwd=str(tmp_path))
    assert result.success
    assert result.output == "here"


def test_run_command_timeout() -> None:
    with mock.patch(
        "council_agent.tools.shell.subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd=["echo"], timeout=1),
    ):
        result = run_command("echo hello", timeout_sec=1)
    assert not result.success
    assert result.error is not None
    assert "timed out" in result.error.lower()
    assert "duration_ms" in result.metadata
