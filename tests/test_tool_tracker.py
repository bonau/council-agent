"""Tests for ToolCallTracker."""

from council_agent.tools.base import ToolResult
from council_agent.tools.tracker import ToolCallTracker


def _fake_tool(*, value: str = "ok") -> ToolResult:
    return ToolResult(success=True, output=value)


def test_tracker_records_calls() -> None:
    tracker = ToolCallTracker(max_tool_calls=5)
    summary = tracker.record("read_file", {"path": "a.txt"}, _fake_tool, value="content")

    assert summary is not None
    assert summary.tool == "read_file"
    assert summary.success is True
    assert len(tracker.summaries) == 1
    assert tracker.remaining == 4


def test_tracker_enforces_limit() -> None:
    tracker = ToolCallTracker(max_tool_calls=2)
    assert tracker.record("t1", {}, _fake_tool) is not None
    assert tracker.record("t2", {}, _fake_tool) is not None
    assert tracker.record("t3", {}, _fake_tool) is None
    assert tracker.limit_reached is True
    assert len(tracker.summaries) == 2


def test_tracker_record_result() -> None:
    tracker = ToolCallTracker(max_tool_calls=10)
    result = ToolResult(
        success=False,
        output="",
        error="fail",
        metadata={"exit_code": 1, "passed": 2, "failed": 1},
    )
    summary = tracker.record_result("run_tests", {"path": "."}, result)

    assert summary is not None
    assert summary.metadata["exit_code"] == 1
    assert summary.metadata["failed"] == 1
