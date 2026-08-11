"""Tests for orchestrator pipeline."""

from unittest.mock import MagicMock, patch

import pytest

from council_agent.config.presets import get_preset_by_name
from council_agent.orchestrator import run_council
from council_agent.security import (
    ConfirmMode,
    get_confirmation_policy,
    without_security_context,
)
from council_agent.types import (
    ExecutionResult,
    PlanArtifact,
    VerdictStatus,
    VerificationVerdict,
)

PRESETS_DIR = __import__("pathlib").Path(__file__).resolve().parents[1] / "presets"


@pytest.fixture(autouse=True)
def no_default_security_context(workspace_root) -> None:
    with without_security_context():
        yield


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


@patch("council_agent.orchestrator.build_planning_crew")
@patch("council_agent.orchestrator.build_execution_crew")
@patch("council_agent.orchestrator.build_verification_crew")
def test_run_council_installs_and_resets_confirm_policy(
    mock_verify_build: MagicMock,
    mock_exec_build: MagicMock,
    mock_plan_build: MagicMock,
) -> None:
    preset = get_preset_by_name(PRESETS_DIR, "glm-stack")
    plan = PlanArtifact(raw="{}", steps=["a"], success_criteria=[], risks=[])
    execution = ExecutionResult(raw="result")
    verdict = VerificationVerdict(
        status=VerdictStatus.PASS,
        raw='{"status": "PASS"}',
        issues=[],
        summary="ok",
    )
    seen: list[ConfirmMode] = []

    def _capture_exec(*_args, **_kwargs):
        seen.append(get_confirmation_policy().mode)
        return execution

    with (
        patch("council_agent.orchestrator.run_planning", return_value=plan),
        patch(
            "council_agent.orchestrator.run_execution",
            side_effect=_capture_exec,
        ),
        patch("council_agent.orchestrator.run_verification", return_value=verdict),
    ):
        run_council(
            "test prompt",
            preset,
            "fake-key",
            confirm_mode=ConfirmMode.AUTO,
        )

    assert seen == [ConfirmMode.AUTO]
    assert get_confirmation_policy().mode is ConfirmMode.COMPAT


@patch("council_agent.orchestrator.build_planning_crew")
@patch("council_agent.orchestrator.build_execution_crew")
@patch("council_agent.orchestrator.build_verification_crew")
def test_run_council_installs_and_resets_audit_logger(
    mock_verify_build: MagicMock,
    mock_exec_build: MagicMock,
    mock_plan_build: MagicMock,
    tmp_path,
    monkeypatch,
) -> None:
    from pathlib import Path

    from council_agent.sandbox.config import apply_workspace_root, init_sandbox
    from council_agent.security import (
        get_audit_logger,
        get_security_context,
        load_audit_events,
    )
    from council_agent.security.audit import default_audit_events_path

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    init_sandbox(tmp_path)
    apply_workspace_root(tmp_path)
    monkeypatch.chdir(tmp_path)

    preset = get_preset_by_name(PRESETS_DIR, "glm-stack")
    plan = PlanArtifact(raw="{}", steps=["a"], success_criteria=[], risks=[])
    execution = ExecutionResult(raw="result")
    verdict = VerificationVerdict(
        status=VerdictStatus.PASS,
        raw='{"status": "PASS"}',
        issues=[],
        summary="ok",
    )
    seen_session_ids: list[str | None] = []

    def _capture_exec(*_args, **_kwargs):
        context = get_security_context()
        assert context is not None
        logger = get_audit_logger()
        assert logger is not None
        assert context.audit_logger is logger
        assert context.session is not None
        assert context.session_id == logger.session_id
        seen_session_ids.append(logger.session_id)
        logger.record("probe", {"x": 1}, success=True)
        return execution

    with (
        patch("council_agent.orchestrator.run_planning", return_value=plan),
        patch(
            "council_agent.orchestrator.run_execution",
            side_effect=_capture_exec,
        ),
        patch("council_agent.orchestrator.run_verification", return_value=verdict),
    ):
        run_council(
            "audit probe",
            preset,
            "fake-key",
            project_root=Path(tmp_path),
        )

    assert get_audit_logger() is None
    assert len(seen_session_ids) == 1
    assert seen_session_ids[0]
    events = load_audit_events(default_audit_events_path(tmp_path))
    assert len(events) == 1
    assert events[0].tool == "probe"
    assert events[0].session_id == seen_session_ids[0]


@patch("council_agent.orchestrator.build_planning_crew")
@patch("council_agent.orchestrator.build_execution_crew")
@patch("council_agent.orchestrator.build_verification_crew")
def test_run_council_without_sandbox_skips_audit_logger(
    mock_verify_build: MagicMock,
    mock_exec_build: MagicMock,
    mock_plan_build: MagicMock,
    tmp_path,
    monkeypatch,
) -> None:
    from council_agent.sandbox.config import apply_workspace_root
    from council_agent.security import get_audit_logger, get_security_context

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    apply_workspace_root(tmp_path)
    monkeypatch.chdir(tmp_path)

    preset = get_preset_by_name(PRESETS_DIR, "glm-stack")
    plan = PlanArtifact(raw="{}", steps=["a"], success_criteria=[], risks=[])
    execution = ExecutionResult(raw="result")
    verdict = VerificationVerdict(
        status=VerdictStatus.PASS,
        raw="{}",
        issues=[],
        summary="ok",
    )
    seen: list[bool] = []

    def _capture_exec(*_args, **_kwargs):
        context = get_security_context()
        assert context is not None
        assert context.session is None
        assert context.audit_logger is None
        seen.append(get_audit_logger() is None)
        return execution

    with (
        patch("council_agent.orchestrator.run_planning", return_value=plan),
        patch(
            "council_agent.orchestrator.run_execution",
            side_effect=_capture_exec,
        ),
        patch("council_agent.orchestrator.run_verification", return_value=verdict),
    ):
        run_council("no audit", preset, "fake-key")

    assert seen == [True]
    assert get_audit_logger() is None
    assert not (tmp_path / ".council" / "audit").exists()


@patch("council_agent.orchestrator.build_planning_crew")
@patch("council_agent.orchestrator.build_execution_crew")
@patch("council_agent.orchestrator.build_verification_crew")
def test_run_council_installs_and_resets_project_policy(
    mock_verify_build: MagicMock,
    mock_exec_build: MagicMock,
    mock_plan_build: MagicMock,
    tmp_path,
    monkeypatch,
) -> None:
    from pathlib import Path

    from council_agent.sandbox.config import apply_workspace_root
    from council_agent.security import get_active_policy

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    apply_workspace_root(tmp_path)
    monkeypatch.chdir(tmp_path)
    (tmp_path / "council.policy.yaml").write_text(
        "schema_version: 1\ndenied_commands:\n  - \"curl *\"\n",
        encoding="utf-8",
    )

    preset = get_preset_by_name(PRESETS_DIR, "glm-stack")
    plan = PlanArtifact(raw="{}", steps=["a"], success_criteria=[], risks=[])
    execution = ExecutionResult(raw="result")
    verdict = VerificationVerdict(
        status=VerdictStatus.PASS,
        raw="{}",
        issues=[],
        summary="ok",
    )
    seen_denied: list[list[str]] = []

    def _capture_exec(*_args, **_kwargs):
        policy = get_active_policy()
        assert policy is not None
        seen_denied.append(list(policy.denied_commands))
        return execution

    with (
        patch("council_agent.orchestrator.run_planning", return_value=plan),
        patch(
            "council_agent.orchestrator.run_execution",
            side_effect=_capture_exec,
        ),
        patch("council_agent.orchestrator.run_verification", return_value=verdict),
    ):
        run_council(
            "policy probe",
            preset,
            "fake-key",
            project_root=Path(tmp_path),
        )

    assert seen_denied == [["curl *"]]
    assert get_active_policy() is None


@patch("council_agent.orchestrator.build_planning_crew")
@patch("council_agent.orchestrator.build_execution_crew")
@patch("council_agent.orchestrator.build_verification_crew")
def test_run_council_invalid_policy_fails_before_crews(
    mock_verify_build: MagicMock,
    mock_exec_build: MagicMock,
    mock_plan_build: MagicMock,
    tmp_path,
    monkeypatch,
) -> None:
    from pathlib import Path

    import pytest

    from council_agent.sandbox.config import apply_workspace_root
    from council_agent.security import PolicyValidationError

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    apply_workspace_root(tmp_path)
    monkeypatch.chdir(tmp_path)
    (tmp_path / "council.policy.yaml").write_text(
        "schema_version: 1\ndenied_commands: not-a-list\n",
        encoding="utf-8",
    )

    preset = get_preset_by_name(PRESETS_DIR, "glm-stack")

    with (
        patch("council_agent.orchestrator.run_planning") as mock_plan_run,
        patch("council_agent.orchestrator.run_execution") as mock_exec_run,
        patch("council_agent.orchestrator.run_verification") as mock_verify_run,
    ):
        with pytest.raises(PolicyValidationError):
            run_council(
                "bad policy",
                preset,
                "fake-key",
                project_root=Path(tmp_path),
            )

    mock_plan_run.assert_not_called()
    mock_exec_run.assert_not_called()
    mock_verify_run.assert_not_called()


@patch("council_agent.orchestrator.build_planning_crew")
@patch("council_agent.orchestrator.build_execution_crew")
@patch("council_agent.orchestrator.build_verification_crew")
def test_run_council_missing_policy_uses_defaults(
    mock_verify_build: MagicMock,
    mock_exec_build: MagicMock,
    mock_plan_build: MagicMock,
    tmp_path,
    monkeypatch,
) -> None:
    from council_agent.sandbox.config import apply_workspace_root
    from council_agent.security import get_active_policy

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    apply_workspace_root(tmp_path)
    monkeypatch.chdir(tmp_path)

    preset = get_preset_by_name(PRESETS_DIR, "glm-stack")
    plan = PlanArtifact(raw="{}", steps=["a"], success_criteria=[], risks=[])
    execution = ExecutionResult(raw="result")
    verdict = VerificationVerdict(
        status=VerdictStatus.PASS,
        raw="{}",
        issues=[],
        summary="ok",
    )
    seen: list[bool] = []

    def _capture_exec(*_args, **_kwargs):
        seen.append(get_active_policy() is None)
        return execution

    with (
        patch("council_agent.orchestrator.run_planning", return_value=plan),
        patch(
            "council_agent.orchestrator.run_execution",
            side_effect=_capture_exec,
        ),
        patch("council_agent.orchestrator.run_verification", return_value=verdict),
    ):
        run_council("no policy file", preset, "fake-key")

    assert seen == [True]
    assert get_active_policy() is None


@patch("council_agent.orchestrator.build_planning_crew")
@patch("council_agent.orchestrator.build_execution_crew")
@patch("council_agent.orchestrator.build_verification_crew")
def test_run_council_uses_one_security_context_snapshot(
    mock_verify_build: MagicMock,
    mock_exec_build: MagicMock,
    mock_plan_build: MagicMock,
) -> None:
    from council_agent.security import (
        ConfirmMode,
        get_security_context,
    )

    preset = get_preset_by_name(PRESETS_DIR, "glm-stack")
    plan = PlanArtifact(raw="{}", steps=["a"], success_criteria=[], risks=[])
    execution = ExecutionResult(raw="result")
    verdict = VerificationVerdict(
        status=VerdictStatus.PASS,
        raw="{}",
        issues=[],
        summary="ok",
    )
    seen_contexts: list[object] = []

    def _capture(value):
        def _run(*_args, **_kwargs):
            context = get_security_context()
            assert context is not None
            seen_contexts.append(context)
            return value

        return _run

    with (
        patch(
            "council_agent.orchestrator.run_planning",
            side_effect=_capture(plan),
        ),
        patch(
            "council_agent.orchestrator.run_execution",
            side_effect=_capture(execution),
        ),
        patch(
            "council_agent.orchestrator.run_verification",
            side_effect=_capture(verdict),
        ),
    ):
        run_council(
            "one context",
            preset,
            "fake-key",
            confirm_mode=ConfirmMode.AUTO,
        )

    assert len(seen_contexts) == 3
    assert all(context is seen_contexts[0] for context in seen_contexts)
    context = seen_contexts[0]
    assert context.confirmation.mode is ConfirmMode.AUTO
    assert context.policy_version == "v0.9-unversioned"
    assert get_security_context() is None


@patch("council_agent.orchestrator.build_planning_crew")
@patch("council_agent.orchestrator.build_execution_crew")
@patch("council_agent.orchestrator.build_verification_crew")
def test_run_council_exception_closes_security_context(
    mock_verify_build: MagicMock,
    mock_exec_build: MagicMock,
    mock_plan_build: MagicMock,
) -> None:
    from council_agent.security import get_security_context

    preset = get_preset_by_name(PRESETS_DIR, "glm-stack")
    seen_active: list[bool] = []

    def _fail(*_args, **_kwargs):
        seen_active.append(get_security_context() is not None)
        raise RuntimeError("planning failed")

    with patch("council_agent.orchestrator.run_planning", side_effect=_fail):
        with pytest.raises(RuntimeError, match="planning failed"):
            run_council("fails", preset, "fake-key")

    assert seen_active == [True]
    assert get_security_context() is None
