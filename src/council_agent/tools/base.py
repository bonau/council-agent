"""Shared types and helpers for council agent tools."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolResult:
    """Unified return structure for all tool functions."""

    success: bool
    output: str
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


def _ok(output: str = "", **metadata: Any) -> ToolResult:
    return ToolResult(success=True, output=output, metadata=dict(metadata))


def _err(error: str, output: str = "", **metadata: Any) -> ToolResult:
    return ToolResult(success=False, output=output, error=error, metadata=dict(metadata))
