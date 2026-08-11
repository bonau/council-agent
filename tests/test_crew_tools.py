"""Tests for CrewAI execution tool wrappers and crew mounting."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from council_agent.config.presets import get_preset_by_name
from council_agent.crews.execution import build_execution_crew, run_execution
from council_agent.crews.execution_tools import LIMIT_MESSAGE, build_execution_tools
from council_agent.sandbox.config import init_sandbox
from council_agent.sandbox.session import SessionManager
from council_agent.tools import ToolCallTracker, ToolResult
from council_agent.types import PlanArtifact

PRESETS_DIR = Path(__file__).resolve().parents[1] / "presets"


def _tools_by_name(tracker: ToolCallTracker, session: SessionManager | None = None):
    tools = build_execution_tools(tracker, session=session)
    return {t.name: t for t in tools}


def test_build_execution_tools_exposes_six_tools() -> None:
    tracker = ToolCallTracker(max_tool_calls=10)
    tools = build_execution_tools(tracker)
    names = {t.name for t in tools}
    assert names == {
        "read_file",
        "write_file",
        "list_dir",
        "delete_file",
        "run_command",
        "run_tests",
    }


def test_read_write_list_delete_via_wrappers(workspace_root: Path) -> None:
    tracker = ToolCallTracker(max_tool_calls=20)
    tools = _tools_by_name(tracker)

    written = tools["write_file"].run(path="note.txt", content="hello")
    assert "hello" in written or "succeeded" in written.lower()

    listed = tools["list_dir"].run(path=".")
    assert "note.txt" in listed

    read = tools["read_file"].run(path="note.txt")
    assert "hello" in read

    deleted = tools["delete_file"].run(path="note.txt")
    assert "ERROR" not in deleted
    assert not (workspace_root / "note.txt").exists()

    assert len(tracker.summaries) == 4
    assert all(s.success for s in tracker.summaries)


def test_run_command_wrapper(workspace_root: Path) -> None:
    tracker = ToolCallTracker(max_tool_calls=5)
    tools = _tools_by_name(tracker)
    out = tools["run_command"].run(command="echo hi-from-tool")
    assert "hi-from-tool" in out
    assert tracker.summaries[0].tool == "run_command"
    assert tracker.summaries[0].success is True


def test_tracker_limit_blocks_underlying_call(workspace_root: Path) -> None:
    tracker = ToolCallTracker(max_tool_calls=1)
    tools = _tools_by_name(tracker)

    tools["write_file"].run(path="a.txt", content="one")
    second = tools["write_file"].run(path="b.txt", content="two")

    assert second == LIMIT_MESSAGE.format(max_tool_calls=1)
    assert len(tracker.summaries) == 1
    assert tracker.limit_reached is True
    assert not (workspace_root / "b.txt").exists()


def test_wrapper_appends_to_session(workspace_root: Path) -> None:
    init_sandbox(workspace_root)
    session = SessionManager.create(
        prompt="p",
        preset="glm-stack",
        workspace_root=workspace_root,
        project_root=workspace_root,
    )
    tracker = ToolCallTracker(max_tool_calls=5)
    tools = _tools_by_name(tracker, session=session)

    tools["write_file"].run(path="x.txt", content="y")
    assert session.meta.tool_call_count == 1
    assert session.count_tool_lines() == 1


def test_wrapper_appends_to_audit_when_logger_installed(workspace_root: Path) -> None:
    from council_agent.security import (
        AuditLogger,
        default_audit_events_path,
        get_audit_logger,
        load_audit_events,
        reset_audit_logger,
        set_audit_logger,
    )

    init_sandbox(workspace_root)
    session = SessionManager.create(
        prompt="p",
        preset="glm-stack",
        workspace_root=workspace_root,
        project_root=workspace_root,
    )
    logger = AuditLogger(
        default_audit_events_path(workspace_root),
        session_id=session.meta.session_id,
    )
    token = set_audit_logger(logger)
    try:
        tracker = ToolCallTracker(max_tool_calls=5)
        tools = _tools_by_name(tracker, session=session)
        tools["write_file"].run(path="audited.txt", content="z")
    finally:
        reset_audit_logger(token)

    assert get_audit_logger() is None
    events = load_audit_events(default_audit_events_path(workspace_root))
    assert len(events) == 1
    assert events[0].tool == "write_file"
    assert events[0].args["path"] == "audited.txt"
    assert events[0].session_id == session.meta.session_id
    assert events[0].success is True
    assert session.count_tool_lines() == 1


@patch("council_agent.crews.execution.Crew")
@patch("council_agent.crews.execution.Task")
@patch("council_agent.crews.execution.Agent")
@patch("council_agent.crews.execution.make_llm")
def test_build_execution_crew_mounts_tools(
    mock_llm: MagicMock,
    mock_agent: MagicMock,
    mock_task: MagicMock,
    mock_crew: MagicMock,
) -> None:
    mock_llm.return_value = MagicMock()
    agent_instance = MagicMock()
    mock_agent.return_value = agent_instance
    crew_instance = MagicMock()
    mock_crew.return_value = crew_instance
    preset = get_preset_by_name(PRESETS_DIR, "glm-stack")
    tracker = ToolCallTracker(max_tool_calls=10)

    result = build_execution_crew(preset, "fake-key", tracker=tracker)
    assert result is crew_instance

    kwargs = mock_agent.call_args.kwargs
    tool_names = {t.name for t in kwargs["tools"]}
    assert tool_names == {
        "read_file",
        "write_file",
        "list_dir",
        "delete_file",
        "run_command",
        "run_tests",
    }


@patch("council_agent.crews.execution.Crew")
@patch("council_agent.crews.execution.Task")
@patch("council_agent.crews.execution.Agent")
@patch("council_agent.crews.execution.make_llm")
def test_build_execution_crew_without_tracker_has_no_tools(
    mock_llm: MagicMock,
    mock_agent: MagicMock,
    mock_task: MagicMock,
    mock_crew: MagicMock,
) -> None:
    mock_llm.return_value = MagicMock()
    preset = get_preset_by_name(PRESETS_DIR, "glm-stack")
    build_execution_crew(preset, "fake-key")
    assert mock_agent.call_args.kwargs["tools"] == []


def test_run_execution_fills_tool_summaries_from_tracker() -> None:
    plan = PlanArtifact(raw="{}", steps=["a"], success_criteria=[], risks=[])
    tracker = ToolCallTracker(max_tool_calls=5)
    tracker.record_result(
        "list_dir",
        {"path": "."},
        ToolResult(
            success=True, output="a.txt", metadata={"entries": ["a.txt"]}
        ),
    )

    mock_crew = MagicMock()
    mock_crew.kickoff.return_value = MagicMock(raw="done")

    with patch(
        "council_agent.crews.execution.crew_output_text", return_value="done"
    ):
        result = run_execution(mock_crew, "prompt", plan, tracker=tracker)

    assert result.raw == "done"
    assert len(result.tool_summaries) == 1
    assert result.tool_summaries[0].tool == "list_dir"
