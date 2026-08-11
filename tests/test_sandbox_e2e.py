"""End-to-end sandbox run with mocked LLM and real tools/session."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from council_agent.config.presets import get_preset_by_name
from council_agent.config.settings import get_settings
from council_agent.crews.execution_tools import build_execution_tools
from council_agent.orchestrator import run_council
from council_agent.sandbox.config import apply_workspace_root, init_sandbox
from council_agent.sandbox.session import SessionManager
from council_agent.sandbox.workspace import get_workspace_guard
from council_agent.security import without_security_context
from council_agent.types import (
    PlanArtifact,
    VerdictStatus,
    VerificationVerdict,
)

PRESETS_DIR = Path(__file__).resolve().parents[1] / "presets"


@pytest.fixture(autouse=True)
def no_default_security_context(workspace_root: Path) -> None:
    with without_security_context():
        yield


def _mock_execution_build(preset, api_key, *, tracker=None, session=None):
    """Build a fake crew whose kickoff invokes real tool wrappers."""
    assert tracker is not None
    tools = {t.name: t for t in build_execution_tools(tracker, session=session)}

    crew = MagicMock()

    def _kickoff(inputs=None, **kwargs):
        tools["write_file"].run(path="hello.txt", content="from-e2e")
        tools["list_dir"].run(path=".")
        tools["run_command"].run(command="echo e2e-ok")
        return MagicMock(raw="wrote hello.txt and listed workspace")

    crew.kickoff.side_effect = _kickoff
    return crew


def test_e2e_run_with_sandbox_writes_files_and_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    get_settings.cache_clear()
    get_workspace_guard.cache_clear()

    init_sandbox(tmp_path)
    apply_workspace_root(tmp_path)
    monkeypatch.chdir(tmp_path)

    preset = get_preset_by_name(PRESETS_DIR, "glm-stack")
    plan = PlanArtifact(
        raw="{}",
        steps=["write hello.txt"],
        success_criteria=["file exists"],
        risks=[],
    )
    verdict = VerificationVerdict(
        status=VerdictStatus.PASS,
        raw='{"status":"PASS"}',
        issues=[],
        summary="ok",
    )

    with (
        patch(
            "council_agent.orchestrator.build_planning_crew",
            return_value=MagicMock(),
        ),
        patch(
            "council_agent.orchestrator.run_planning",
            return_value=plan,
        ),
        patch(
            "council_agent.orchestrator.build_execution_crew",
            side_effect=_mock_execution_build,
        ),
        patch(
            "council_agent.orchestrator.build_verification_crew",
            return_value=MagicMock(),
        ),
        patch(
            "council_agent.orchestrator.run_verification",
            return_value=verdict,
        ),
    ):
        result = run_council(
            "create hello.txt",
            preset,
            "test-key",
            project_root=tmp_path,
        )

    assert (tmp_path / "hello.txt").read_text(encoding="utf-8") == "from-e2e"
    assert len(result.execution.tool_summaries) == 3
    assert {s.tool for s in result.execution.tool_summaries} == {
        "write_file",
        "list_dir",
        "run_command",
    }
    assert all(s.success for s in result.execution.tool_summaries)

    latest = SessionManager.latest(tmp_path)
    assert latest is not None
    assert latest.meta.prompt == "create hello.txt"
    assert latest.meta.preset == "glm-stack"
    assert latest.meta.status == "completed"
    assert latest.meta.ended_at is not None
    assert latest.meta.tool_call_count == 3
    assert latest.count_tool_lines() == 3

    lines = [
        json.loads(line)
        for line in latest.tools_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert lines[0]["tool"] == "write_file"
    assert lines[0]["args"]["path"] == "hello.txt"


def test_e2e_run_with_sandbox_writes_audit_events(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from council_agent.security import get_audit_logger, load_audit_events
    from council_agent.security.audit import default_audit_events_path

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    get_settings.cache_clear()
    get_workspace_guard.cache_clear()

    init_sandbox(tmp_path)
    apply_workspace_root(tmp_path)
    monkeypatch.chdir(tmp_path)

    preset = get_preset_by_name(PRESETS_DIR, "glm-stack")
    plan = PlanArtifact(
        raw="{}",
        steps=["write hello.txt"],
        success_criteria=["file exists"],
        risks=[],
    )
    verdict = VerificationVerdict(
        status=VerdictStatus.PASS,
        raw='{"status":"PASS"}',
        issues=[],
        summary="ok",
    )

    with (
        patch(
            "council_agent.orchestrator.build_planning_crew",
            return_value=MagicMock(),
        ),
        patch(
            "council_agent.orchestrator.run_planning",
            return_value=plan,
        ),
        patch(
            "council_agent.orchestrator.build_execution_crew",
            side_effect=_mock_execution_build,
        ),
        patch(
            "council_agent.orchestrator.build_verification_crew",
            return_value=MagicMock(),
        ),
        patch(
            "council_agent.orchestrator.run_verification",
            return_value=verdict,
        ),
    ):
        run_council(
            "create hello.txt",
            preset,
            "test-key",
            project_root=tmp_path,
        )

    assert get_audit_logger() is None
    events = load_audit_events(default_audit_events_path(tmp_path))
    assert len(events) == 3
    assert {e.tool for e in events} == {"write_file", "list_dir", "run_command"}
    session = SessionManager.latest(tmp_path)
    assert session is not None
    assert all(e.session_id == session.meta.session_id for e in events)
    assert session.count_tool_lines() == 3


def test_e2e_run_without_sandbox_skips_session_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    get_settings.cache_clear()
    get_workspace_guard.cache_clear()
    apply_workspace_root(tmp_path)
    monkeypatch.chdir(tmp_path)

    preset = get_preset_by_name(PRESETS_DIR, "glm-stack")
    plan = PlanArtifact(raw="{}", steps=["a"], success_criteria=[], risks=[])
    verdict = VerificationVerdict(
        status=VerdictStatus.PASS,
        raw="{}",
        issues=[],
        summary="ok",
    )

    with (
        patch(
            "council_agent.orchestrator.build_planning_crew",
            return_value=MagicMock(),
        ),
        patch(
            "council_agent.orchestrator.run_planning",
            return_value=plan,
        ),
        patch(
            "council_agent.orchestrator.build_execution_crew",
            side_effect=_mock_execution_build,
        ),
        patch(
            "council_agent.orchestrator.build_verification_crew",
            return_value=MagicMock(),
        ),
        patch(
            "council_agent.orchestrator.run_verification",
            return_value=verdict,
        ),
    ):
        result = run_council("no sandbox", preset, "test-key")

    assert (tmp_path / "hello.txt").exists()
    assert len(result.execution.tool_summaries) == 3
    assert not (tmp_path / ".council").exists()
    assert SessionManager.latest(tmp_path) is None


def test_existing_orchestrator_api_still_works_without_kwargs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Zero-modification compatibility: positional args only."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    get_settings.cache_clear()
    apply_workspace_root(tmp_path)

    preset = get_preset_by_name(PRESETS_DIR, "glm-stack")
    plan = PlanArtifact(raw="{}", steps=[], success_criteria=[], risks=[])
    from council_agent.types import ExecutionResult

    execution = ExecutionResult(raw="ok")
    verdict = VerificationVerdict(
        status=VerdictStatus.PASS, raw="{}", issues=[], summary="ok"
    )

    with (
        patch(
            "council_agent.orchestrator.build_planning_crew",
            return_value=MagicMock(),
        ),
        patch(
            "council_agent.orchestrator.build_execution_crew",
            return_value=MagicMock(),
        ) as mock_exec_build,
        patch(
            "council_agent.orchestrator.build_verification_crew",
            return_value=MagicMock(),
        ),
        patch("council_agent.orchestrator.run_planning", return_value=plan),
        patch(
            "council_agent.orchestrator.run_execution", return_value=execution
        ),
        patch(
            "council_agent.orchestrator.run_verification", return_value=verdict
        ),
    ):
        result = run_council("compat", preset, "test-key")

    assert result.final_output == "ok"
    assert "tracker" in mock_exec_build.call_args.kwargs
    assert mock_exec_build.call_args.kwargs["session"] is None
