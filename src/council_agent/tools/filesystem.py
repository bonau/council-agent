"""Filesystem tools: read, write, list, delete."""

from __future__ import annotations

from pathlib import Path

from council_agent.sandbox.workspace import WorkspaceGuardError, get_workspace_guard
from council_agent.security import ActionKind, require_confirmation
from council_agent.tools.base import ToolResult, _err, _ok

_ENCODING = "utf-8"


def read_file(path: str) -> ToolResult:
    try:
        target = get_workspace_guard().resolve(path)
    except WorkspaceGuardError as exc:
        return _err(str(exc))
    try:
        if not target.exists():
            return _err(f"File not found: {path}")
        if target.is_dir():
            return _err(f"Path is a directory, not a file: {path}")
        content = target.read_text(encoding=_ENCODING)
        data = content.encode(_ENCODING)
        return _ok(content, size=len(data), encoding=_ENCODING)
    except PermissionError:
        return _err(f"Permission denied: {path}")
    except OSError as exc:
        return _err(str(exc))


def write_file(path: str, content: str) -> ToolResult:
    try:
        target = get_workspace_guard().resolve(path)
    except WorkspaceGuardError as exc:
        return _err(str(exc))

    decision = require_confirmation(ActionKind.WRITE_FILE, path)
    confirm_meta: dict[str, str] = {}
    if decision.outcome.value != "compat_allow":
        confirm_meta["confirmation"] = decision.outcome.value
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


def list_dir(path: str) -> ToolResult:
    try:
        target = get_workspace_guard().resolve(path)
    except WorkspaceGuardError as exc:
        return _err(str(exc))
    try:
        if not target.exists():
            return _err(f"Directory not found: {path}")
        if not target.is_dir():
            return _err(f"Path is not a directory: {path}")
        entries = sorted(entry.name for entry in target.iterdir())
        names = "\n".join(entries)
        return _ok(names, entries=entries)
    except PermissionError:
        return _err(f"Permission denied: {path}")
    except OSError as exc:
        return _err(str(exc))


def delete_file(path: str) -> ToolResult:
    try:
        target = get_workspace_guard().resolve(path)
    except WorkspaceGuardError as exc:
        return _err(str(exc))

    decision = require_confirmation(ActionKind.DELETE_FILE, path)
    confirm_meta: dict[str, str] = {}
    if decision.outcome.value != "compat_allow":
        confirm_meta["confirmation"] = decision.outcome.value
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
