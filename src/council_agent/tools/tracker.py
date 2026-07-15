"""Tool call tracking and max_tool_calls enforcement."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from council_agent.tools.base import ToolResult
from council_agent.types import ToolCallSummary


class ToolCallTracker:
    """Record tool invocations and enforce a per-run call limit."""

    def __init__(self, max_tool_calls: int = 50) -> None:
        self.max_tool_calls = max_tool_calls
        self.summaries: list[ToolCallSummary] = []
        self.limit_reached = False

    @property
    def remaining(self) -> int:
        return max(0, self.max_tool_calls - len(self.summaries))

    def record(
        self,
        name: str,
        args: dict[str, Any],
        fn: Callable[..., ToolResult],
        **kwargs: Any,
    ) -> ToolCallSummary | None:
        if len(self.summaries) >= self.max_tool_calls:
            self.limit_reached = True
            return None

        result = fn(**kwargs)
        summary = ToolCallSummary.from_result(name, args, result)
        self.summaries.append(summary)
        return summary

    def record_result(
        self,
        name: str,
        args: dict[str, Any],
        result: ToolResult,
    ) -> ToolCallSummary | None:
        if len(self.summaries) >= self.max_tool_calls:
            self.limit_reached = True
            return None

        summary = ToolCallSummary.from_result(name, args, result)
        self.summaries.append(summary)
        return summary
