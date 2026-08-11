"""Shell tools: run_command, run_tests."""

from __future__ import annotations

import re
import subprocess
import sys
import time
from typing import Any

from council_agent.sandbox.workspace import WorkspaceGuardError, get_workspace_guard
from council_agent.security import (
    ActionKind,
    CommandCategory,
    classify_command,
    evaluate_command_policy,
    require_confirmation,
)
from council_agent.tools.base import ToolResult, _err, _ok

_SUMMARY_LINE = re.compile(
    r"(?:(\d+)\s+passed)?(?:,\s*)?(?:(\d+)\s+failed)?(?:,\s*)?"
    r"(?:(\d+)\s+skipped)?(?:,\s*)?(?:(\d+)\s+error)?",
    re.IGNORECASE,
)
_FAILURE_LINE = re.compile(r"^(?:FAILED|E\s+).+", re.MULTILINE)


def parse_pytest_output(combined: str, exit_code: int) -> dict[str, Any]:
    """Extract passed/failed/skipped counts and failure summaries from pytest output."""
    passed = failed = skipped = errors = 0
    for match in _SUMMARY_LINE.finditer(combined):
        if match.group(1) is not None:
            passed = int(match.group(1))
        if match.group(2) is not None:
            failed = int(match.group(2))
        if match.group(3) is not None:
            skipped = int(match.group(3))
        if match.group(4) is not None:
            errors = int(match.group(4))

    if exit_code != 0 and passed == 0 and failed == 0 and skipped == 0 and errors == 0:
        failed = 1

    failures = [
        line.strip()
        for line in _FAILURE_LINE.findall(combined)
        if line.strip()
    ]

    return {
        "exit_code": exit_code,
        "passed": passed,
        "failed": failed + errors,
        "skipped": skipped,
        "failures": failures,
    }


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

    if not command or not command.strip():
        return _err("Empty command")

    policy_decision = evaluate_command_policy(command)
    if not policy_decision.allowed:
        reason = (
            policy_decision.reason.value
            if policy_decision.reason is not None
            else "denied"
        )
        meta: dict[str, Any] = {"policy_decision": reason}
        if policy_decision.matched_pattern is not None:
            meta["policy_pattern"] = policy_decision.matched_pattern
            detail = f"matched: {policy_decision.matched_pattern}"
        else:
            detail = "not in allowed_commands"
        return _err(f"Command denied by policy ({reason}; {detail})", **meta)

    classification = classify_command(command)
    class_meta: dict[str, Any] = {"classification": classification.category.value}
    if classification.matched_rule is not None:
        class_meta["matched_rule"] = classification.matched_rule

    gate_kind: ActionKind | None = None
    if classification.category is CommandCategory.DANGEROUS:
        gate_kind = ActionKind.DANGEROUS_SHELL
    elif classification.category is CommandCategory.WRITE:
        gate_kind = ActionKind.WRITE_SHELL

    if gate_kind is not None:
        decision = require_confirmation(gate_kind, command)
        if decision.outcome.value != "compat_allow":
            class_meta["confirmation"] = decision.outcome.value
        if not decision.allowed:
            rule = classification.matched_rule or "unknown"
            label = classification.category.value
            return _err(
                f"Command classified as {label} (matched: {rule}); "
                f"confirmation {decision.outcome.value}",
                **class_meta,
            )

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
            **class_meta,
        )
    except OSError as exc:
        duration_ms = int((time.monotonic() - start) * 1000)
        return _err(str(exc), duration_ms=duration_ms, **class_meta)

    duration_ms = int((time.monotonic() - start) * 1000)
    stdout = result.stdout
    if stdout.endswith("\n"):
        stdout = stdout[:-1]

    stderr = result.stderr.strip() if result.stderr else None
    metadata = {
        "exit_code": result.returncode,
        "duration_ms": duration_ms,
        **class_meta,
    }

    if result.returncode == 0:
        return _ok(stdout, **metadata)

    error = stderr or f"Command exited with code {result.returncode}"
    return _err(error, output=stdout, **metadata)


def run_tests(
    path: str = ".",
    args: str = "",
    *,
    timeout_sec: int = 120,
) -> ToolResult:
    try:
        test_path = get_workspace_guard().resolve(path)
    except WorkspaceGuardError as exc:
        return _err(str(exc))

    if not test_path.exists():
        return _err(f"Test path does not exist: {path}")

    cmd_parts = [
        sys.executable,
        "-m",
        "pytest",
        str(test_path),
        "-q",
        "--tb=line",
    ]
    if args.strip():
        cmd_parts.extend(args.split())

    command = " ".join(cmd_parts)
    result = run_command(command, timeout_sec=timeout_sec)

    combined = result.output
    if result.error:
        combined = f"{combined}\n{result.error}".strip()

    exit_code = int(result.metadata.get("exit_code", 1))
    parsed = parse_pytest_output(combined, exit_code)
    metadata = {**result.metadata, **parsed}

    if result.success:
        return _ok(result.output, **metadata)

    error = result.error or f"Tests failed with exit code {exit_code}"
    return _err(error, output=result.output, **metadata)
