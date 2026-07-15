"""Integration tests: real tools + verification pipeline wiring."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from council_agent.config.presets import get_effective_max_tool_calls, get_preset_by_name
from council_agent.crews.verification import _format_tool_summaries, run_verification
from council_agent.tools import ToolCallTracker, run_tests
from council_agent.types import (
    ExecutionResult,
    PlanArtifact,
    ToolCallSummary,
    VerdictStatus,
)

PRESETS_DIR = Path(__file__).resolve().parents[1] / "presets"


def test_format_tool_summaries_includes_test_counts() -> None:
    summaries = [
        ToolCallSummary(
            tool="run_tests",
            success=False,
            output="1 failed, 2 passed",
            error="Tests failed",
            metadata={
                "exit_code": 1,
                "passed": 2,
                "failed": 1,
                "skipped": 0,
                "failures": ["E   assert False"],
            },
        )
    ]
    text = _format_tool_summaries(summaries)
    assert "run_tests" in text
    assert "exit_code=1" in text
    assert "failed=1" in text
    assert "failures=" in text


def test_run_verification_passes_tool_summaries_to_crew() -> None:
    plan = PlanArtifact(
        raw="{}",
        steps=["run tests"],
        success_criteria=["all tests pass"],
        risks=[],
    )
    summaries = [
        ToolCallSummary(
            tool="run_tests",
            success=True,
            output="3 passed",
            error=None,
            metadata={"exit_code": 0, "passed": 3, "failed": 0, "skipped": 0},
        )
    ]
    execution = ExecutionResult(raw="done", tool_summaries=summaries)

    mock_crew = MagicMock()
    mock_crew.kickoff.return_value = MagicMock(
        raw='{"status": "PASS", "summary": "ok", "issues": []}'
    )

    with patch(
        "council_agent.crews.verification.extract_json_block",
        return_value={"status": "PASS", "summary": "ok", "issues": []},
    ):
        verdict = run_verification(mock_crew, "prompt", plan, execution)

    assert verdict.status == VerdictStatus.PASS
    kickoff_inputs = mock_crew.kickoff.call_args.kwargs["inputs"]
    assert "exit_code=0" in kickoff_inputs["tool_summaries"]
    assert "passed=3" in kickoff_inputs["tool_summaries"]


def test_real_run_tests_via_tracker(workspace_root: Path) -> None:
    tests_dir = workspace_root / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_ok.py").write_text(
        "def test_ok():\n    assert True\n",
        encoding="utf-8",
    )

    tracker = ToolCallTracker(max_tool_calls=5)
    summary = tracker.record("run_tests", {"path": "tests"}, run_tests, path="tests")

    assert summary is not None
    assert summary.success is True
    assert summary.metadata["exit_code"] == 0
    assert summary.metadata["passed"] >= 1


def test_preset_max_tool_calls_default() -> None:
    preset = get_preset_by_name(PRESETS_DIR, "glm-stack")
    assert get_effective_max_tool_calls(preset) == 50
