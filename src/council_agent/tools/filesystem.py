"""Filesystem tools: read, write, list, delete."""

from __future__ import annotations

from pathlib import Path

from council_agent.sandbox.workspace import (
    DeniedPathError,
    WorkspaceBoundaryError,
    WorkspaceGuardError,
)
from council_agent.security.confirm import (
    ActionKind,
    evaluate_tier_aware_confirmation,
)
from council_agent.security.middleware import (
    SecurityContext,
    _register_tool,
    invoke,
)
from council_agent.tools.base import ToolResult, _err, _ok

_ENCODING = "utf-8"


def _guard_error(error: WorkspaceGuardError) -> ToolResult:
    if isinstance(error, DeniedPathError):
        reason = "denied_path"
    elif isinstance(error, WorkspaceBoundaryError):
        reason = "workspace_boundary"
    else:
        reason = "workspace_guard"
    return _err(str(error), rejection_reason=reason)


def _confirm_meta(decision_outcome: str) -> dict[str, str]:
    if decision_outcome == "compat_allow":
        return {}
    return {"confirmation": decision_outcome}


def _read_file(context: SecurityContext, *, path: str) -> ToolResult:
    context.validate(require_active=True)
    try:
        target = context.workspace.resolve(path)
    except WorkspaceGuardError as exc:
        return _guard_error(exc)

    decision = evaluate_tier_aware_confirmation(
        context.confirmation,
        ActionKind.READ_FILE,
        path,
    )
    confirm_meta = _confirm_meta(decision.outcome.value)
    if not decision.allowed:
        return _err(
            f"read_file confirmation {decision.outcome.value}: {path}",
            **confirm_meta,
        )

    try:
        if not target.exists():
            return _err(f"File not found: {path}", **confirm_meta)
        if target.is_dir():
            return _err(f"Path is a directory, not a file: {path}", **confirm_meta)
        content = target.read_text(encoding=_ENCODING)
        data = content.encode(_ENCODING)
        return _ok(content, size=len(data), encoding=_ENCODING, **confirm_meta)
    except PermissionError:
        return _err(f"Permission denied: {path}", **confirm_meta)
    except OSError as exc:
        return _err(str(exc), **confirm_meta)


def _write_file(
    context: SecurityContext,
    *,
    path: str,
    content: str,
) -> ToolResult:
    context.validate(require_active=True)
    try:
        target = context.workspace.resolve(path)
    except WorkspaceGuardError as exc:
        return _guard_error(exc)

    decision = evaluate_tier_aware_confirmation(
        context.confirmation,
        ActionKind.WRITE_FILE,
        path,
    )
    confirm_meta = _confirm_meta(decision.outcome.value)
    if not decision.allowed:
        return _err(
            f"write_file confirmation {decision.outcome.value}: {path}",
            **confirm_meta,
        )

    try:
        created = not target.exists()
        target.parent.mkdir(parents=True, exist_ok=True)
        data = content.encode(_ENCODING)
        target.write_text(content, encoding=_ENCODING)
        return _ok(content, bytes_written=len(data), created=created, **confirm_meta)
    except PermissionError:
        return _err(f"Permission denied: {path}", **confirm_meta)
    except OSError as exc:
        return _err(str(exc), **confirm_meta)


def _list_dir(context: SecurityContext, *, path: str) -> ToolResult:
    context.validate(require_active=True)
    try:
        target = context.workspace.resolve(path)
    except WorkspaceGuardError as exc:
        return _guard_error(exc)

    decision = evaluate_tier_aware_confirmation(
        context.confirmation,
        ActionKind.READ_FILE,
        path,
    )
    confirm_meta = _confirm_meta(decision.outcome.value)
    if not decision.allowed:
        return _err(
            f"list_dir confirmation {decision.outcome.value}: {path}",
            **confirm_meta,
        )

    try:
        if not target.exists():
            return _err(f"Directory not found: {path}", **confirm_meta)
        if not target.is_dir():
            return _err(f"Path is not a directory: {path}", **confirm_meta)
        entries = sorted(entry.name for entry in target.iterdir())
        names = "\n".join(entries)
        return _ok(names, entries=entries, **confirm_meta)
    except PermissionError:
        return _err(f"Permission denied: {path}", **confirm_meta)
    except OSError as exc:
        return _err(str(exc), **confirm_meta)


def _delete_file(context: SecurityContext, *, path: str) -> ToolResult:
    context.validate(require_active=True)
    try:
        target = context.workspace.resolve(path)
    except WorkspaceGuardError as exc:
        return _guard_error(exc)

    decision = evaluate_tier_aware_confirmation(
        context.confirmation,
        ActionKind.DELETE_FILE,
        path,
    )
    confirm_meta = _confirm_meta(decision.outcome.value)
    if not decision.allowed:
        return _err(
            f"delete_file confirmation {decision.outcome.value}: {path}",
            **confirm_meta,
        )

    try:
        if not target.exists():
            return _err(f"File not found: {path}", **confirm_meta)
        if target.is_dir():
            return _err(f"Path is a directory, not a file: {path}", **confirm_meta)
        target.unlink()
        return _ok(deleted=True, **confirm_meta)
    except PermissionError:
        return _err(f"Permission denied: {path}", **confirm_meta)
    except OSError as exc:
        return _err(str(exc), **confirm_meta)


def read_file(path: str) -> ToolResult:
    """Read a UTF-8 file through the mandatory policy dispatcher."""

    return invoke("read_file", path=path)


def write_file(path: str, content: str) -> ToolResult:
    """Write a UTF-8 file through the mandatory policy dispatcher."""

    return invoke("write_file", path=path, content=content)


def list_dir(path: str) -> ToolResult:
    """List a directory through the mandatory policy dispatcher."""

    return invoke("list_dir", path=path)


def delete_file(path: str) -> ToolResult:
    """Delete a file through the mandatory policy dispatcher."""

    return invoke("delete_file", path=path)


_register_tool("read_file", _read_file)
_register_tool("write_file", _write_file)
_register_tool("list_dir", _list_dir)
_register_tool("delete_file", _delete_file)
