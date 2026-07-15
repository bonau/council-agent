"""Filesystem tools: read, write, list, delete."""

from __future__ import annotations

from pathlib import Path

from council_agent.tools.base import ToolResult, _err, _ok

_ENCODING = "utf-8"


def read_file(path: str) -> ToolResult:
    target = Path(path)
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
    target = Path(path)
    try:
        created = not target.exists()
        target.parent.mkdir(parents=True, exist_ok=True)
        data = content.encode(_ENCODING)
        target.write_text(content, encoding=_ENCODING)
        return _ok(content, bytes_written=len(data), created=created)
    except PermissionError:
        return _err(f"Permission denied: {path}")
    except OSError as exc:
        return _err(str(exc))


def list_dir(path: str) -> ToolResult:
    target = Path(path)
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
    target = Path(path)
    try:
        if not target.exists():
            return _err(f"File not found: {path}")
        if target.is_dir():
            return _err(f"Path is a directory, not a file: {path}")
        target.unlink()
        return _ok(deleted=True)
    except PermissionError:
        return _err(f"Permission denied: {path}")
    except OSError as exc:
        return _err(str(exc))
