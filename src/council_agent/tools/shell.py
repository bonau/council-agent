"""Shell tools: run_command, run_tests."""

from __future__ import annotations

import re
import shlex
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from council_agent.sandbox.workspace import (
    DeniedPathError,
    WorkspaceGuardError,
)
from council_agent.security.classifier import (
    ClassificationResult,
    CommandCategory,
    RejectedCommandAnalysis,
    classify_command,
)
from council_agent.security.confirm import ActionKind, evaluate_confirmation
from council_agent.security.middleware import (
    SecurityContext,
    _register_tool,
    invoke,
)
from council_agent.security.policy import evaluate_command
from council_agent.tools.base import ToolResult, _err, _ok
from council_agent.tools.pytest_args import RejectedPytestArgs, parse_pytest_args

_SUMMARY_LINE = re.compile(
    r"(?:(\d+)\s+passed)?(?:,\s*)?(?:(\d+)\s+failed)?(?:,\s*)?"
    r"(?:(\d+)\s+skipped)?(?:,\s*)?(?:(\d+)\s+error)?",
    re.IGNORECASE,
)
_FAILURE_LINE = re.compile(r"^(?:FAILED|E\s+).+", re.MULTILINE)


@dataclass(frozen=True)
class _PreparedAction:
    """An authorized action's stable display and retained execution argv."""

    display_argv: tuple[str, ...]
    execution_argv: tuple[str, ...]
    category: CommandCategory
    matched_rule: str

    @property
    def canonical_command(self) -> str:
        return shlex.join(self.display_argv)


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


def _guard_refusal(exc: WorkspaceGuardError) -> ToolResult:
    if isinstance(exc, DeniedPathError):
        reason = "denied_path"
    else:
        reason = "workspace_boundary"
    return _err(str(exc), rejection_reason=reason)


def _analysis_refusal(analysis: RejectedCommandAnalysis) -> ToolResult:
    return _err(
        analysis.error,
        rejection_reason=analysis.rejection_reason.value,
    )


def _classification_metadata(action: _PreparedAction) -> dict[str, Any]:
    return {
        "classification": action.category.value,
        "matched_rule": action.matched_rule,
    }


def _prepare_command_action(
    analysis: ClassificationResult,
) -> _PreparedAction | ToolResult:
    """Resolve a bare executable once and retain it for shell-free execution."""

    executable = shutil.which(analysis.argv[0])
    if executable is None:
        return _err(
            f"Supported executable is not available: {analysis.argv[0]}",
            rejection_reason="unsupported",
            classification=analysis.category.value,
            matched_rule=analysis.matched_rule,
        )
    return _PreparedAction(
        display_argv=analysis.argv,
        execution_argv=(str(Path(executable).resolve()), *analysis.argv[1:]),
        category=analysis.category,
        matched_rule=analysis.matched_rule,
    )


def _authorize_action(
    context: SecurityContext,
    action: _PreparedAction,
) -> dict[str, Any] | ToolResult:
    """Apply project policy and confirmation to one canonical action."""

    context.validate(require_active=True)
    class_meta = _classification_metadata(action)
    policy_decision = evaluate_command(action.canonical_command, context.policy)
    if not policy_decision.allowed:
        reason = (
            policy_decision.reason.value
            if policy_decision.reason is not None
            else "denied"
        )
        meta: dict[str, Any] = {**class_meta, "policy_decision": reason}
        if policy_decision.matched_pattern is not None:
            meta["policy_pattern"] = policy_decision.matched_pattern
            detail = f"matched: {policy_decision.matched_pattern}"
        else:
            detail = "not in allowed_commands"
        return _err(f"Command denied by policy ({reason}; {detail})", **meta)

    gate_kind: ActionKind | None = None
    if action.category is CommandCategory.DANGEROUS:
        gate_kind = ActionKind.DANGEROUS_SHELL
    elif action.category is CommandCategory.WRITE:
        gate_kind = ActionKind.WRITE_SHELL

    if gate_kind is None:
        return class_meta

    decision = evaluate_confirmation(
        context.confirmation,
        gate_kind,
        action.canonical_command,
    )
    if decision.outcome.value != "compat_allow":
        class_meta["confirmation"] = decision.outcome.value
    if decision.allowed:
        return class_meta
    return _err(
        f"Command classified as {action.category.value} "
        f"(matched: {action.matched_rule}); confirmation {decision.outcome.value}",
        **class_meta,
    )


def _execute_prepared(
    context: SecurityContext,
    action: _PreparedAction,
    *,
    workdir: Path,
    timeout_sec: int,
    authorization_meta: dict[str, Any] | None = None,
) -> ToolResult:
    """Execute retained argv directly, with no serialization or shell."""

    context.validate(require_active=True)
    class_meta = authorization_meta or _classification_metadata(action)
    start = time.monotonic()
    try:
        result = subprocess.run(
            list(action.execution_argv),
            shell=False,
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
    return _err(
        stderr or f"Command exited with code {result.returncode}",
        output=stdout,
        **metadata,
    )


def _run_command(
    context: SecurityContext,
    *,
    command: str,
    cwd: str | None = None,
    *,
    timeout_sec: int = 120,
) -> ToolResult:
    context.validate(require_active=True)
    guard = context.workspace
    try:
        workdir = guard.resolve_cwd(cwd)
    except WorkspaceGuardError as exc:
        return _guard_refusal(exc)

    analysis = classify_command(command)
    if isinstance(analysis, RejectedCommandAnalysis):
        return _analysis_refusal(analysis)

    try:
        for operand in analysis.path_operands:
            guard.resolve_from(workdir, operand)
    except WorkspaceGuardError as exc:
        refusal = _guard_refusal(exc)
        refusal.metadata.update(
            classification=analysis.category.value,
            matched_rule=analysis.matched_rule,
        )
        return refusal

    prepared = _prepare_command_action(analysis)
    if isinstance(prepared, ToolResult):
        return prepared
    authorization = _authorize_action(context, prepared)
    if isinstance(authorization, ToolResult):
        return authorization
    return _execute_prepared(
        context,
        prepared,
        workdir=workdir,
        timeout_sec=timeout_sec,
        authorization_meta=authorization,
    )


def _run_tests(
    context: SecurityContext,
    *,
    path: str = ".",
    args: str = "",
    *,
    timeout_sec: int = 120,
) -> ToolResult:
    context.validate(require_active=True)
    guard = context.workspace
    try:
        test_path = guard.resolve(path)
    except WorkspaceGuardError as exc:
        return _guard_refusal(exc)

    if not test_path.exists():
        return _err(
            f"Test path does not exist: {path}",
            rejection_reason="unsupported",
        )

    parsed_args = parse_pytest_args(args)
    if isinstance(parsed_args, RejectedPytestArgs):
        return _err(
            parsed_args.error,
            rejection_reason=parsed_args.rejection_reason.value,
        )
    try:
        for operand in parsed_args.path_operands:
            guard.resolve_from(guard.root, operand)
    except WorkspaceGuardError as exc:
        return _guard_refusal(exc)

    action_argv = (
        sys.executable,
        "-m",
        "pytest",
        str(test_path),
        "-q",
        "--tb=line",
        *parsed_args.argv,
    )
    action = _PreparedAction(
        display_argv=action_argv,
        execution_argv=action_argv,
        category=CommandCategory.WRITE,
        matched_rule="run-tests",
    )
    authorization = _authorize_action(context, action)
    if isinstance(authorization, ToolResult):
        return authorization
    result = _execute_prepared(
        context,
        action,
        workdir=guard.root,
        timeout_sec=timeout_sec,
        authorization_meta=authorization,
    )

    combined = result.output
    if result.error:
        combined = f"{combined}\n{result.error}".strip()

    if "exit_code" not in result.metadata:
        return result
    exit_code = int(result.metadata["exit_code"])
    parsed = parse_pytest_output(combined, exit_code)
    metadata = {**result.metadata, **parsed}

    if result.success:
        return _ok(result.output, **metadata)

    error = result.error or f"Tests failed with exit code {exit_code}"
    return _err(error, output=result.output, **metadata)


def run_command(
    command: str,
    cwd: str | None = None,
    *,
    timeout_sec: int = 120,
) -> ToolResult:
    """Run one supported command through the mandatory policy dispatcher."""

    return invoke(
        "run_command",
        command=command,
        cwd=cwd,
        timeout_sec=timeout_sec,
    )


def run_tests(
    path: str = ".",
    args: str = "",
    *,
    timeout_sec: int = 120,
) -> ToolResult:
    """Run pytest through the mandatory policy dispatcher."""

    return invoke(
        "run_tests",
        path=path,
        args=args,
        timeout_sec=timeout_sec,
    )


_register_tool("run_command", _run_command)
_register_tool("run_tests", _run_tests)
