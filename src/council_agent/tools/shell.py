"""Shell tools: run_command."""

from __future__ import annotations

import subprocess
import time

from council_agent.sandbox.workspace import WorkspaceGuardError, get_workspace_guard
from council_agent.tools.base import ToolResult, _err, _ok


def run_command(
    command: str,
    cwd: str | None = None,
    *,
    timeout_sec: int = 120,
) -> ToolResult:
    try:
        workdir = get_workspace_guard().resolve_cwd(cwd)
    except WorkspaceGuardError as exc:
        return _err(str(exc))

    start = time.monotonic()
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            cwd=str(workdir),
            timeout=timeout_sec,
        )
    except subprocess.TimeoutExpired:
        duration_ms = int((time.monotonic() - start) * 1000)
        return _err(
            f"Command timed out after {timeout_sec}s",
            duration_ms=duration_ms,
        )
    except OSError as exc:
        duration_ms = int((time.monotonic() - start) * 1000)
        return _err(str(exc), duration_ms=duration_ms)

    duration_ms = int((time.monotonic() - start) * 1000)
    stdout = result.stdout
    if stdout.endswith("\n"):
        stdout = stdout[:-1]

    stderr = result.stderr.strip() if result.stderr else None
    metadata = {"exit_code": result.returncode, "duration_ms": duration_ms}

    if result.returncode == 0:
        return _ok(stdout, **metadata)

    error = stderr or f"Command exited with code {result.returncode}"
    return _err(error, output=stdout, **metadata)
