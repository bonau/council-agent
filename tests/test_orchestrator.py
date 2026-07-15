"""Tests for orchestrator pipeline."""

from unittest.mock import MagicMock, patch

from council_agent.config.presets import get_preset_by_name
from council_agent.orchestrator import run_council
from council_agent.types import (
    ExecutionResult,
    PlanArtifact,
    VerdictStatus,
    VerificationVerdict,
)

PRESETS_DIR = __import__("pathlib").Path(__file__).resolve().parents[1] / "presets"


@patch("council_agent.orchestrator.build_planning_crew")
@patch("council_agent.orchestrator.build_execution_crew")
@patch("council_agent.orchestrator.build_verification_crew")
def test_run_council_pass_no_escalation(
    mock_verify_build: MagicMock,
    mock_exec_build: MagicMock,
    mock_plan_build: MagicMock,
) -> None:
    preset = get_preset_by_name(PRESETS_DIR, "glm-stack")
    plan = PlanArtifact(
        raw='{"steps": ["a"]}',
        steps=["a"],
        success_criteria=["done"],
        risks=[],
    )
    execution = ExecutionResult(raw="result")
    verdict = VerificationVerdict(
        status=VerdictStatus.PASS,
        raw='{"status": "PASS"}',
        issues=[],
        summary="All good",
    )

    with (
        patch(
            "council_agent.orchestrator.run_planning", return_value=plan
        ) as mock_plan,
        patch(
            "council_agent.orchestrator.run_execution", return_value=execution
        ) as mock_exec,
        patch(
            "council_agent.orchestrator.run_verification", return_value=verdict
        ) as mock_verify,
        patch("council_agent.orchestrator.build_escalation_crew") as mock_esc,
    ):
        result = run_council("test prompt", preset, "fake-key")

    mock_plan_build.assert_called_once()
    mock_exec_build.assert_called_once()
    mock_verify_build.assert_called_once()
    mock_plan.assert_called_once()
    mock_exec.assert_called_once()
    mock_verify.assert_called_once()
    mock_esc.assert_not_called()

    assert result.escalated is False
    assert result.final_output == "result"
    assert result.verdict.status == VerdictStatus.PASS


@patch("council_agent.orchestrator.build_planning_crew")
@patch("council_agent.orchestrator.build_execution_crew")
@patch("council_agent.orchestrator.build_verification_crew")
@patch("council_agent.orchestrator.build_escalation_crew")
def test_run_council_fail_triggers_escalation(
    mock_esc_build: MagicMock,
    mock_verify_build: MagicMock,
    mock_exec_build: MagicMock,
    mock_plan_build: MagicMock,
) -> None:
    preset = get_preset_by_name(PRESETS_DIR, "glm-stack")
    plan = PlanArtifact(raw="{}", steps=["a"], success_criteria=[], risks=[])
    execution = ExecutionResult(raw="initial")
    fail_verdict = VerificationVerdict(
        status=VerdictStatus.FAIL,
        raw='{"status": "FAIL"}',
        issues=["missing detail"],
        summary="Incomplete",
    )
    escalated = ExecutionResult(raw="fixed result")

    with (
        patch("council_agent.orchestrator.run_planning", return_value=plan),
        patch("council_agent.orchestrator.run_execution", return_value=execution),
        patch(
            "council_agent.orchestrator.run_verification", return_value=fail_verdict
        ),
        patch(
            "council_agent.orchestrator.run_escalation", return_value=escalated
        ) as mock_esc_run,
    ):
        result = run_council("test prompt", preset, "fake-key")

    mock_esc_build.assert_called_once()
    mock_esc_run.assert_called_once()
    assert result.escalated is True
    assert result.final_output == "fixed result"
