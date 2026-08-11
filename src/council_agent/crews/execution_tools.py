"""CrewAI `@tool` wrappers for Execution Crew (must not live under tools/)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from crewai.tools import tool

from council_agent.tools import (
    ToolResult,
    delete_file,
    list_dir,
    read_file,
    run_command,
    run_tests,
    write_file,
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
    name: str,
    fn: Callable[..., ToolResult],
    **kwargs: Any,
) -> str:
    return _format_result(name, fn(**kwargs))


def build_execution_tools() -> list[Any]:
    """Build six CrewAI adapters over dispatcher-backed public tool APIs."""

    @tool("read_file")
    def read_file_tool(path: str) -> str:
        """Read a UTF-8 text file inside the workspace. Path is relative to workspace root."""
        return _invoke(
            "read_file",
            read_file,
            path=path,
        )

    @tool("write_file")
    def write_file_tool(path: str, content: str) -> str:
        """Write UTF-8 text to a file inside the workspace, creating parents as needed."""
        return _invoke(
            "write_file",
            write_file,
            path=path,
            content=content,
        )

    @tool("list_dir")
    def list_dir_tool(path: str) -> str:
        """List names of entries in a workspace directory (one name per line)."""
        return _invoke(
            "list_dir",
            list_dir,
            path=path,
        )

    @tool("delete_file")
    def delete_file_tool(path: str) -> str:
        """Delete a file inside the workspace. Directories are not removed."""
        return _invoke(
            "delete_file",
            delete_file,
            path=path,
        )

    @tool("run_command")
    def run_command_tool(command: str, cwd: str | None = None) -> str:
        """Run a shell command inside the workspace (cwd defaults to workspace root)."""
        return _invoke(
            "run_command",
            run_command,
            command=command,
            cwd=cwd,
        )

    @tool("run_tests")
    def run_tests_tool(path: str = ".", args: str = "") -> str:
        """Run pytest on a workspace path and return structured pass/fail output."""
        return _invoke(
            "run_tests",
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
