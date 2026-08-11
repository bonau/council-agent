"""CLI tests for sandbox init/status and --workspace."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from council_agent.cli import app
from council_agent.config.settings import get_settings
from council_agent.llm.openrouter import OpenRouterCredential
from council_agent.sandbox.config import is_sandbox_initialized
from council_agent.sandbox.session import SessionManager
from council_agent.sandbox.workspace import get_workspace_guard
from council_agent.security import Principal, PrincipalScope
from council_agent.types import (
    CouncilResult,
    ExecutionResult,
    PlanArtifact,
    VerdictStatus,
    VerificationVerdict,
)

runner = CliRunner()


def _fake_result() -> CouncilResult:
    return CouncilResult(
        prompt="hi",
        plan=PlanArtifact(raw="{}", steps=[], success_criteria=[], risks=[]),
        execution=ExecutionResult(raw="done"),
        verdict=VerificationVerdict(
            status=VerdictStatus.PASS,
            raw="{}",
            issues=[],
            summary="ok",
        ),
        escalated=False,
        final_output="done",
    )


def test_sandbox_init_creates_council_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["sandbox", "init"])

    assert result.exit_code == 0, result.output
    assert is_sandbox_initialized(tmp_path)
    assert "initialized" in result.output.lower()
    assert (tmp_path / ".council" / "config.yaml").is_file()
    assert (tmp_path / ".council" / "sessions").is_dir()


def test_sandbox_init_idempotent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    assert runner.invoke(app, ["sandbox", "init"]).exit_code == 0
    session = SessionManager.create(
        prompt="keep",
        preset="glm-stack",
        workspace_root=tmp_path,
        project_root=tmp_path,
    )
    session_dir = session.session_dir

    result = runner.invoke(app, ["sandbox", "init"])
    assert result.exit_code == 0, result.output
    assert "already initialized" in result.output.lower()
    assert session_dir.is_dir()


def test_sandbox_init_with_workspace_flag(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    project.mkdir()
    result = runner.invoke(app, ["sandbox", "init", "--workspace", str(project)])

    assert result.exit_code == 0, result.output
    assert is_sandbox_initialized(project)
    assert get_settings().council_workspace_root == project.resolve()
    assert get_workspace_guard().root == project.resolve()


def test_sandbox_status_not_initialized(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["sandbox", "status"])

    assert result.exit_code == 0, result.output
    assert "Initialized" in result.output
    assert "no" in result.output.lower()


def test_sandbox_status_with_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    assert runner.invoke(app, ["sandbox", "init"]).exit_code == 0
    session = SessionManager.create(
        prompt="status me",
        preset="glm-stack",
        workspace_root=tmp_path,
        project_root=tmp_path,
    )
    session.append_tool_call("list_dir", {"path": "."}, success=True)
    session.finalize()

    result = runner.invoke(app, ["sandbox", "status"])
    assert result.exit_code == 0, result.output
    assert "Initialized" in result.output
    assert "yes" in result.output.lower()
    assert session.meta.session_id in result.output
    assert "tool_calls=1" in result.output
    assert "status me" in result.output


def test_run_workspace_flag_applies_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    get_settings.cache_clear()
    project = tmp_path / "run-ws"
    project.mkdir()

    fake = CouncilResult(
        prompt="hi",
        plan=PlanArtifact(raw="{}", steps=[], success_criteria=[], risks=[]),
        execution=ExecutionResult(raw="done"),
        verdict=VerificationVerdict(
            status=VerdictStatus.PASS,
            raw="{}",
            issues=[],
            summary="ok",
        ),
        escalated=False,
        final_output="done",
    )

    with patch("council_agent.cli.run_council", return_value=fake) as mock_run:
        result = runner.invoke(
            app,
            ["run", "hi", "--workspace", str(project)],
        )

    assert result.exit_code == 0, result.output
    mock_run.assert_called_once()
    assert get_settings().council_workspace_root == project.resolve()
    assert get_workspace_guard().root == project.resolve()
    assert "Workspace" in result.output
    assert project.name in result.output
    credential = mock_run.call_args.kwargs["provider_credential"]
    principal = mock_run.call_args.kwargs["principal"]
    assert isinstance(credential, OpenRouterCredential)
    assert credential.get_secret_value() == "test-key"
    assert isinstance(principal, Principal)
    assert principal.principal_id != "test-key"
    # CliRunner stdin is not a TTY → refuse unless --yes
    assert mock_run.call_args.kwargs.get("confirm_mode").value == "refuse"


def test_run_yes_flag_passes_auto_confirm_mode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    get_settings.cache_clear()

    fake = CouncilResult(
        prompt="hi",
        plan=PlanArtifact(raw="{}", steps=[], success_criteria=[], risks=[]),
        execution=ExecutionResult(raw="done"),
        verdict=VerificationVerdict(
            status=VerdictStatus.PASS,
            raw="{}",
            issues=[],
            summary="ok",
        ),
        escalated=False,
        final_output="done",
    )

    with patch("council_agent.cli.run_council", return_value=fake) as mock_run:
        result = runner.invoke(app, ["run", "hi", "--yes"])

    assert result.exit_code == 0, result.output
    assert mock_run.call_args.kwargs.get("confirm_mode").value == "auto"
    assert "Confirm" in result.output
    assert "auto" in result.output


def test_run_loads_read_only_principal_separately_from_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "provider-only-secret")
    monkeypatch.setenv("COUNCIL_PRINCIPAL_ID", "local-test-principal")
    monkeypatch.setenv("COUNCIL_PRINCIPAL_SCOPES", "read")
    get_settings.cache_clear()

    with patch(
        "council_agent.cli.run_council",
        return_value=_fake_result(),
    ) as mock_run:
        result = runner.invoke(app, ["run", "hi"])

    assert result.exit_code == 0, result.output
    credential = mock_run.call_args.kwargs["provider_credential"]
    principal = mock_run.call_args.kwargs["principal"]
    assert credential.get_secret_value() == "provider-only-secret"
    assert principal.principal_id == "local-test-principal"
    assert principal.scopes == frozenset({PrincipalScope.READ})
    assert "local-test-principal" not in result.output
    assert principal.audit_ref in result.output


def test_run_rejects_unknown_principal_scope_before_pipeline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    unknown = "sk-or-v1-unknown-scope-secret"
    monkeypatch.setenv("OPENROUTER_API_KEY", "provider-only-secret")
    monkeypatch.setenv("COUNCIL_PRINCIPAL_SCOPES", f"read,{unknown}")
    get_settings.cache_clear()

    with patch("council_agent.cli.run_council") as mock_run:
        result = runner.invoke(app, ["run", "hi"])

    assert result.exit_code == 2
    assert "Configuration Error" in result.output
    assert "Unknown Council principal scope" in result.output
    assert unknown not in result.output
    mock_run.assert_not_called()
