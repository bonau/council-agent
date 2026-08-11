"""Tests for CrewAI execution tool wrappers and crew mounting."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from council_agent.config.presets import get_preset_by_name
from council_agent.crews.execution import build_execution_crew, run_execution
from council_agent.crews.execution_tools import build_execution_tools
from council_agent.sandbox.config import init_sandbox
from council_agent.sandbox.session import SessionManager
from council_agent.security import (
    AuditLogger,
    SecurityContext,
    default_audit_events_path,
    get_security_context,
    load_audit_events,
    security_context,
    without_security_context,
)
from council_agent.tools import ToolCallTracker, ToolResult, run_command
from council_agent.types import PlanArtifact

PRESETS_DIR = Path(__file__).resolve().parents[1] / "presets"


def _tools_by_name():
    tools = build_execution_tools()
    return {t.name: t for t in tools}


def test_build_execution_tools_exposes_six_tools() -> None:
    tools = build_execution_tools()
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
    context = get_security_context()
    assert context is not None
    tools = _tools_by_name()

    written = tools["write_file"].run(path="note.txt", content="hello")
    assert "hello" in written or "succeeded" in written.lower()

    listed = tools["list_dir"].run(path=".")
    assert "note.txt" in listed

    read = tools["read_file"].run(path="note.txt")
    assert "hello" in read

    deleted = tools["delete_file"].run(path="note.txt")
    assert "ERROR" not in deleted
    assert not (workspace_root / "note.txt").exists()

    assert len(context.tracker.summaries) == 4
    assert all(s.success for s in context.tracker.summaries)


def test_run_command_wrapper(workspace_root: Path) -> None:
    context = get_security_context()
    assert context is not None
    tools = _tools_by_name()
    out = tools["run_command"].run(command="echo hi-from-tool")
    assert "hi-from-tool" in out
    assert context.tracker.summaries[0].tool == "run_command"
    assert context.tracker.summaries[0].success is True


def test_crew_and_direct_paths_share_denial_decision() -> None:
    context = get_security_context()
    assert context is not None
    direct = run_command("unknown-product-command")
    tools = _tools_by_name()

    formatted = tools["run_command"].run(command="unknown-product-command")
    crew_summary = context.tracker.summaries[-1]

    assert formatted.startswith("ERROR:")
    assert direct.metadata["decision"] == crew_summary.metadata["decision"] == "deny"
    assert (
        direct.metadata["rejection_reason"]
        == crew_summary.metadata["rejection_reason"]
        == "unsupported"
    )


def test_wrapper_without_context_fails_closed(workspace_root: Path) -> None:
    target = workspace_root / "blocked.txt"
    with without_security_context():
        tools = _tools_by_name()
        result = tools["write_file"].run(path="blocked.txt", content="blocked")

    assert result.startswith("ERROR:")
    assert "No SecurityContext is installed" in result
    assert not target.exists()


def test_tracker_limit_blocks_underlying_call(workspace_root: Path) -> None:
    tracker = ToolCallTracker(max_tool_calls=1)
    context = SecurityContext.create(workspace_root, tracker=tracker)
    with without_security_context(), security_context(context):
        tools = _tools_by_name()
        tools["write_file"].run(path="a.txt", content="one")
        second = tools["write_file"].run(path="b.txt", content="two")

    assert second.startswith("ERROR: Tool call limit reached (1).")
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
    context = SecurityContext.create(
        workspace_root,
        tracker=tracker,
        session=session,
    )
    with without_security_context(), security_context(context):
        tools = _tools_by_name()
        tools["write_file"].run(path="x.txt", content="y")
    assert session.meta.tool_call_count == 1
    assert session.count_tool_lines() == 1


def test_wrapper_appends_to_audit_when_logger_installed(workspace_root: Path) -> None:
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
    tracker = ToolCallTracker(max_tool_calls=5)
    context = SecurityContext.create(
        workspace_root,
        tracker=tracker,
        session=session,
        audit_logger=logger,
    )
    with without_security_context(), security_context(context):
        tools = _tools_by_name()
        tools["write_file"].run(path="audited.txt", content="z")

    events = load_audit_events(default_audit_events_path(workspace_root))
    assert len(events) == 2
    assert [event.phase for event in events] == ["attempt", "result"]
    assert all(event.tool == "write_file" for event in events)
    assert all(event.args["path"] == "audited.txt" for event in events)
    assert all(event.session_id == session.meta.session_id for event in events)
    assert events[1].success is True
    assert events[0].action_id == events[1].action_id
    assert len(tracker.summaries) == 1
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
    result = build_execution_crew(preset, "fake-key")
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
def test_build_execution_crew_can_disable_tools(
    mock_llm: MagicMock,
    mock_agent: MagicMock,
    mock_task: MagicMock,
    mock_crew: MagicMock,
) -> None:
    mock_llm.return_value = MagicMock()
    preset = get_preset_by_name(PRESETS_DIR, "glm-stack")
    build_execution_crew(preset, "fake-key", enable_tools=False)
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
