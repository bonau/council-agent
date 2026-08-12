"""CLI, Crew, and library equivalence for trust-decision vectors."""

from __future__ import annotations

from pathlib import Path
from unittest import mock

import pytest
from typer.testing import CliRunner

from council_agent.cli import app
from council_agent.crews.execution_tools import build_execution_tools
from council_agent.security import (
    ActionRisk,
    AuthenticationState,
    AuditLogger,
    ConfirmMode,
    ConfirmationPolicy,
    CouncilPolicy,
    DecisionVector,
    GrantState,
    InteractionState,
    PolicyState,
    Principal,
    PrincipalKind,
    PrincipalScope,
    ScopeState,
    SecurityContext,
    TrustDecisionOutcome,
    TrustDecisionReason,
    evaluate_decision,
    load_audit_events,
    pipeline_attempt,
    resolve_cli_confirm_mode,
    security_context,
    without_security_context,
)
from council_agent.tools import run_command, write_file
from conftest import visible_cli_text

runner = CliRunner()


def _read_only_principal() -> Principal:
    return Principal(
        principal_id="entrypoint-user",
        kind=PrincipalKind.LOCAL_USER,
        issuer="pytest",
        scopes=frozenset({PrincipalScope.READ}),
    )


def _crew_tools() -> dict[str, object]:
    return {tool.name: tool for tool in build_execution_tools()}


def test_direct_and_crew_share_exact_matrix_evidence(tmp_path: Path) -> None:
    audit_path = tmp_path / "audit" / "events.jsonl"
    context = SecurityContext.create(
        tmp_path,
        principal=_read_only_principal(),
        confirmation=ConfirmationPolicy(mode=ConfirmMode.AUTO),
        audit_logger=AuditLogger(audit_path),
    )

    with without_security_context(), security_context(context):
        with pipeline_attempt("entrypoint-attempt"):
            direct = write_file("blocked.txt", "blocked")
            wrapped = _crew_tools()["write_file"].run(
                path="blocked.txt",
                content="blocked",
            )

    result_events = [
        event for event in load_audit_events(audit_path) if event.phase == "result"
    ]
    assert direct.metadata["trust_decision"]["reason"] == "scope_insufficient"
    assert wrapped.startswith("ERROR:")
    assert len(result_events) == 2
    assert {
        event.metadata["pipeline_attempt_id"] for event in result_events
    } == {"entrypoint-attempt"}
    assert (
        result_events[0].metadata["trust_decision"]
        == result_events[1].metadata["trust_decision"]
        == direct.metadata["trust_decision"]
    )
    assert not (tmp_path / "blocked.txt").exists()
    assert context.tracker.summaries == []


def test_cli_resolved_yes_preserves_policy_over_scope_precedence(
    tmp_path: Path,
) -> None:
    mode = resolve_cli_confirm_mode(yes=True, is_tty=False)
    context = SecurityContext.create(
        tmp_path,
        principal=_read_only_principal(),
        confirmation=ConfirmationPolicy(mode=mode),
        policy=CouncilPolicy(
            schema_version=1,
            denied_commands=["mkdir *"],
        ),
    )

    with (
        without_security_context(),
        security_context(context),
        mock.patch("council_agent.tools.shell.subprocess.run") as process,
    ):
        result = run_command("mkdir marker")

    matrix = result.metadata["trust_decision"]
    assert mode is ConfirmMode.AUTO
    assert matrix["reason"] == "policy_denied"
    assert matrix["vector"]["scope"] == "scope_insufficient"
    assert matrix["vector"]["interaction"] == "auto"
    assert process.call_count == 0
    assert not (tmp_path / "marker").exists()


def test_cli_auto_interaction_cannot_override_invalid_grant() -> None:
    mode = resolve_cli_confirm_mode(yes=True, is_tty=True)
    assert mode is ConfirmMode.AUTO

    decision = evaluate_decision(
        DecisionVector(
            policy=PolicyState.ALLOWED,
            scope=ScopeState.ALLOWED,
            authentication=AuthenticationState.SATISFIED,
            grant=GrantState.INVALID,
            risk=ActionRisk.HIGH_RISK,
            interaction=InteractionState.AUTO_APPROVED,
        )
    )

    assert decision.outcome is TrustDecisionOutcome.DENY
    assert decision.reason is TrustDecisionReason.TRUST_GRANT_INVALID


def test_run_help_documents_yes_boundary_and_trust_tier(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # CI enables colour; Rich then splits "--yes" into "-" + "-yes".
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("FORCE_COLOR", "1")
    monkeypatch.setenv("CLICOLOR_FORCE", "1")
    monkeypatch.setenv("TERM", "xterm-256color")
    monkeypatch.setenv("COLUMNS", "80")

    result = runner.invoke(app, ["run", "--help"])
    visible = visible_cli_text(result.output)
    compact = " ".join(visible.lower().split())
    assert result.exit_code == 0, visible
    assert "--yes" in visible
    assert "--trust-tier" in visible
    assert "interaction prompts" in compact
    assert "grant scopes" in compact
    assert "authenticate" in compact
    assert "trust grant" in compact
    assert "elevate privilege" in compact
    assert "independent of --yes" in compact
