"""Orchestrator and CLI wiring tests for session authentication."""

from __future__ import annotations

from pathlib import Path
from unittest import mock

import pytest
from pydantic import SecretStr
from typer.testing import CliRunner

from council_agent.cli import app
from council_agent.config.presets import get_preset_by_name
from council_agent.config.settings import get_settings
from council_agent.llm.openrouter import OpenRouterCredential
from council_agent.orchestrator import run_council
from council_agent.sandbox.config import apply_workspace_root
from council_agent.security import (
    ConfirmMode,
    SecurityContext,
    full_scope_principal,
    get_security_context,
    without_security_context,
)
from council_agent.tools import run_command
from council_agent.types import (
    CouncilResult,
    ExecutionResult,
    PlanArtifact,
    VerdictStatus,
    VerificationVerdict,
)
from conftest import visible_cli_text

PRESETS_DIR = Path(__file__).resolve().parents[1] / "presets"
PROVIDER_CREDENTIAL = OpenRouterCredential("orchestrator-provider")
PRINCIPAL = full_scope_principal("orchestrator-auth", issuer="pytest")
runner = CliRunner()


@pytest.fixture(autouse=True)
def no_default_security_context() -> None:
    with without_security_context():
        yield


def _plan() -> PlanArtifact:
    return PlanArtifact(raw="{}", steps=["remove marker"], success_criteria=[], risks=[])


def _verdict() -> VerificationVerdict:
    return VerificationVerdict(
        status=VerdictStatus.PASS,
        raw='{"status":"PASS"}',
        issues=[],
        summary="ok",
    )


def _fake_result() -> CouncilResult:
    return CouncilResult(
        prompt="hi",
        plan=_plan(),
        execution=ExecutionResult(raw="done"),
        verdict=_verdict(),
        escalated=False,
        final_output="done",
    )


def _run_with_high_risk_action(
    tmp_path: Path,
    *,
    verifier: SecretStr | None,
) -> tuple[object, SecurityContext]:
    preset = get_preset_by_name(PRESETS_DIR, "glm-stack")
    marker = tmp_path / "marker"
    marker.mkdir()
    seen_contexts: list[SecurityContext] = []
    tool_results: list[object] = []

    def _execute(*_args, **_kwargs) -> ExecutionResult:
        context = get_security_context()
        assert context is not None
        seen_contexts.append(context)
        tool_results.append(run_command("rm -rf marker"))
        return ExecutionResult(raw="attempted high-risk action")

    with (
        mock.patch("council_agent.orchestrator.build_planning_crew"),
        mock.patch("council_agent.orchestrator.build_execution_crew"),
        mock.patch("council_agent.orchestrator.build_verification_crew"),
        mock.patch("council_agent.orchestrator.run_planning", return_value=_plan()),
        mock.patch(
            "council_agent.orchestrator.run_execution",
            side_effect=_execute,
        ),
        mock.patch(
            "council_agent.orchestrator.run_verification",
            return_value=_verdict(),
        ),
    ):
        run_council(
            "remove marker",
            preset,
            PROVIDER_CREDENTIAL,
            PRINCIPAL,
            confirm_mode=ConfirmMode.AUTO,
            authentication_verifier=verifier,
        )

    assert len(tool_results) == 1
    assert len(seen_contexts) == 1
    return tool_results[0], seen_contexts[0]


def test_product_context_yes_only_cannot_authenticate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    apply_workspace_root(tmp_path)
    monkeypatch.chdir(tmp_path)

    result, context = _run_with_high_risk_action(tmp_path, verifier=None)

    assert result.success is False
    assert result.metadata["rejection_reason"] == "authentication_missing"
    assert context.confirmation.mode is ConfirmMode.AUTO
    assert context.require_high_risk_step_up is True
    assert context.authentication_manager is None
    assert context.session_id
    assert (tmp_path / "marker").is_dir()


def test_configured_service_verifier_authenticates_and_is_revoked_on_cleanup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    apply_workspace_root(tmp_path)
    monkeypatch.chdir(tmp_path)

    result, context = _run_with_high_risk_action(
        tmp_path,
        verifier=SecretStr("orchestrator-auth-verifier"),
    )

    assert result.success is True
    assert result.metadata["session_authentication"]["reason"] == "step_up_allowed"
    assert context.authentication_manager is not None
    assert context.authentication_manager.revoked is True
    assert context.step_up_provider is not None
    assert not (tmp_path / "marker").exists()
    assert not (tmp_path / ".council").exists()
    assert get_security_context() is None


def test_orchestrator_exception_revokes_authentication_manager(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    apply_workspace_root(tmp_path)
    monkeypatch.chdir(tmp_path)
    preset = get_preset_by_name(PRESETS_DIR, "glm-stack")
    seen: list[SecurityContext] = []

    def _fail(*_args, **_kwargs):
        context = get_security_context()
        assert context is not None
        seen.append(context)
        raise RuntimeError("pipeline failed")

    with (
        mock.patch("council_agent.orchestrator.build_planning_crew"),
        mock.patch("council_agent.orchestrator.build_execution_crew"),
        mock.patch("council_agent.orchestrator.build_verification_crew"),
        mock.patch("council_agent.orchestrator.run_planning", side_effect=_fail),
        pytest.raises(RuntimeError, match="pipeline failed"),
    ):
        run_council(
            "fail after context install",
            preset,
            PROVIDER_CREDENTIAL,
            PRINCIPAL,
            authentication_verifier=SecretStr("exception-auth-verifier"),
        )

    assert len(seen) == 1
    assert seen[0].authentication_manager is not None
    assert seen[0].authentication_manager.revoked is True
    assert get_security_context() is None


def test_orchestrator_rejects_raw_or_empty_auth_verifier_before_runtime(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    apply_workspace_root(tmp_path)
    preset = get_preset_by_name(PRESETS_DIR, "glm-stack")

    with (
        mock.patch("council_agent.orchestrator.SecurityContext.create") as create,
        pytest.raises(TypeError, match="SecretStr"),
    ):
        run_council(
            "raw verifier",
            preset,
            PROVIDER_CREDENTIAL,
            PRINCIPAL,
            authentication_verifier="raw-secret",  # type: ignore[arg-type]
        )
    create.assert_not_called()

    with (
        mock.patch("council_agent.orchestrator.SecurityContext.create") as create,
        pytest.raises(ValueError, match="non-empty"),
    ):
        run_council(
            "empty verifier",
            preset,
            PROVIDER_CREDENTIAL,
            PRINCIPAL,
            authentication_verifier=SecretStr(""),
        )
    create.assert_not_called()


def test_cli_passes_dedicated_secret_without_displaying_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw_auth = "cli-auth-secret-must-not-print"
    raw_provider = "cli-provider-secret-must-not-print"
    monkeypatch.setenv("OPENROUTER_API_KEY", raw_provider)
    monkeypatch.setenv("COUNCIL_AUTH_SECRET", raw_auth)
    get_settings.cache_clear()

    with mock.patch("council_agent.cli.run_council", return_value=_fake_result()) as run:
        result = runner.invoke(app, ["run", "hi", "--yes"])

    assert result.exit_code == 0, result.output
    verifier = run.call_args.kwargs["authentication_verifier"]
    assert isinstance(verifier, SecretStr)
    assert verifier.get_secret_value() == raw_auth
    assert run.call_args.kwargs["confirm_mode"] is ConfirmMode.AUTO
    assert "High-risk step-up" in result.output
    assert "configured" in result.output
    assert raw_auth not in result.output
    assert raw_provider not in result.output


def test_cli_yes_without_verifier_passes_no_authentication(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "provider-only")
    monkeypatch.setenv("COUNCIL_AUTH_SECRET", "")
    get_settings.cache_clear()

    with mock.patch("council_agent.cli.run_council", return_value=_fake_result()) as run:
        result = runner.invoke(app, ["run", "hi", "--yes"])

    assert result.exit_code == 0, result.output
    assert run.call_args.kwargs["authentication_verifier"] is None
    assert run.call_args.kwargs["confirm_mode"] is ConfirmMode.AUTO
    assert "not configured" in result.output


def test_cli_exposes_no_command_line_auth_secret_option() -> None:
    result = runner.invoke(app, ["run", "--help"])
    visible = visible_cli_text(result.output)

    assert result.exit_code == 0, visible
    assert "--auth-secret" not in visible
