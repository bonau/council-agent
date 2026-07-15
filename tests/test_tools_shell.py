"""Tests for shell tools."""

import sys
from pathlib import Path

from council_agent.tools.shell import run_command


def test_run_command_success() -> None:
    result = run_command("echo hello")
    assert result.success
    assert result.output == "hello"
    assert result.metadata["exit_code"] == 0
    assert "duration_ms" in result.metadata


def test_run_command_failure() -> None:
    result = run_command(f"{sys.executable} -c \"import sys; sys.exit(42)\"")
    assert not result.success
    assert result.metadata["exit_code"] == 42
    assert result.error is not None


def test_run_command_stderr() -> None:
    result = run_command(
        f"{sys.executable} -c \"import sys; sys.stderr.write('err'); sys.exit(1)\""
    )
    assert not result.success
    assert result.error == "err"
    assert result.metadata["exit_code"] == 1


def test_run_command_with_cwd(tmp_path: Path) -> None:
    (tmp_path / "marker.txt").write_text("here", encoding="utf-8")
    result = run_command("python -c \"import os; print(os.path.exists('marker.txt'))\"", cwd=str(tmp_path))
    assert result.success
    assert result.output == "True"


def test_run_command_timeout() -> None:
    result = run_command(
        f"{sys.executable} -c \"import time; time.sleep(5)\"",
        timeout_sec=1,
    )
    assert not result.success
    assert result.error is not None
    assert "timed out" in result.error.lower()
    assert "duration_ms" in result.metadata
