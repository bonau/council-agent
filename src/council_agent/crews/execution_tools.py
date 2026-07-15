"""CrewAI `@tool` wrappers for Execution Crew (must not live under tools/)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from crewai.tools import tool

from council_agent.sandbox.session import SessionManager
from council_agent.tools import (
    ToolCallTracker,
    ToolResult,
    delete_file,
    list_dir,
    read_file,
    run_command,
    run_tests,
    write_file,
)
from council_agent.tools.base import ToolResult as TR

LIMIT_MESSAGE = (
    "Tool call limit reached ({max_tool_calls}). "
    "No further tool calls are allowed in this run."
)


def _format_result(name: str, result: ToolResult) -> str:
    if result.success:
        if result.output:
            return result.output
        meta = ", ".join(f"{k}={v}" for k, v in result.metadata.items())
        return f"{name} succeeded" + (f" ({meta})" if meta else "")
    parts = [f"ERROR: {result.error or 'unknown error'}"]
    if result.output:
        parts.append(result.output)
    return "\n".join(parts)


def _invoke(
    tracker: ToolCallTracker,
    session: SessionManager | None,
    name: str,
    args: dict[str, Any],
    fn: Callable[..., TR],
    **kwargs: Any,
) -> str:
    if len(tracker.summaries) >= tracker.max_tool_calls:
        tracker.limit_reached = True
        return LIMIT_MESSAGE.format(max_tool_calls=tracker.max_tool_calls)

    summary = tracker.record(name, args, fn, **kwargs)
    if summary is None:
        return LIMIT_MESSAGE.format(max_tool_calls=tracker.max_tool_calls)

    if session is not None:
        session.append_tool_call(
            name,
            args,
            success=summary.success,
            metadata=summary.metadata,
            output=summary.output,
            error=summary.error,
        )

    result = TR(
        success=summary.success,
        output=summary.output,
        error=summary.error,
        metadata=summary.metadata,
    )
    return _format_result(name, result)


def build_execution_tools(
    tracker: ToolCallTracker,
    session: SessionManager | None = None,
) -> list[Any]:
    """Build six CrewAI tools bound to the given tracker (and optional session)."""

    @tool("read_file")
    def read_file_tool(path: str) -> str:
        """Read a UTF-8 text file inside the workspace. Path is relative to workspace root."""
        return _invoke(
            tracker,
            session,
            "read_file",
            {"path": path},
            read_file,
            path=path,
        )

    @tool("write_file")
    def write_file_tool(path: str, content: str) -> str:
        """Write UTF-8 text to a file inside the workspace, creating parents as needed."""
        return _invoke(
            tracker,
            session,
            "write_file",
            {"path": path, "content": content},
            write_file,
            path=path,
            content=content,
        )

    @tool("list_dir")
    def list_dir_tool(path: str) -> str:
        """List names of entries in a workspace directory (one name per line)."""
        return _invoke(
            tracker,
            session,
            "list_dir",
            {"path": path},
            list_dir,
            path=path,
        )

    @tool("delete_file")
    def delete_file_tool(path: str) -> str:
        """Delete a file inside the workspace. Directories are not removed."""
        return _invoke(
            tracker,
            session,
            "delete_file",
            {"path": path},
            delete_file,
            path=path,
        )

    @tool("run_command")
    def run_command_tool(command: str, cwd: str | None = None) -> str:
        """Run a shell command inside the workspace (cwd defaults to workspace root)."""
        args: dict[str, Any] = {"command": command}
        if cwd is not None:
            args["cwd"] = cwd
        return _invoke(
            tracker,
            session,
            "run_command",
            args,
            run_command,
            command=command,
            cwd=cwd,
        )

    @tool("run_tests")
    def run_tests_tool(path: str = ".", args: str = "") -> str:
        """Run pytest on a workspace path and return structured pass/fail output."""
        return _invoke(
            tracker,
            session,
            "run_tests",
            {"path": path, "args": args},
            run_tests,
            path=path,
            args=args,
        )

    return [
        read_file_tool,
        write_file_tool,
        list_dir_tool,
        delete_file_tool,
        run_command_tool,
        run_tests_tool,
    ]
