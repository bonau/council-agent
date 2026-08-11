"""Council agent tools — reusable file and shell operations."""

from council_agent.tools.base import ToolResult
from council_agent.tools.tracker import ToolCallTracker

__all__ = [
    "ToolResult",
    "ToolCallTracker",
    "delete_file",
    "list_dir",
    "read_file",
    "run_command",
    "run_tests",
    "write_file",
]


def __getattr__(name: str):
    """Load dispatcher-backed product functions without eager import cycles."""

    if name in {"delete_file", "list_dir", "read_file", "write_file"}:
        from council_agent.tools import filesystem

        return getattr(filesystem, name)
    if name in {"run_command", "run_tests"}:
        from council_agent.tools import shell

        return getattr(shell, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
