"""CLI tests for authenticated user-owned trust grant administration."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from typer.testing import CliRunner

from council_agent.cli import app
from council_agent.security.middleware import (
    SecurityContext,
    security_context,
    without_security_context,
)
from council_agent.security.principal import (
    Principal,
    PrincipalKind,
    PrincipalScope,
)
from council_agent.tools.filesystem import write_file
from council_agent.tools.tracker import ToolCallTracker

runner = CliRunner()
UUID_PATTERN = re.compile(
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b"
)
FULL_SCOPES = "read,filesystem:mutate,test,shell,high-risk:manage"


@pytest.fixture
def trust_cli_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[Path, Path]:
    workspace = tmp_path / "project"
    user_data = tmp_path / "user-data"
    workspace.mkdir(mode=0o700)
    user_data.mkdir(mode=0o700)
    monkeypatch.chdir(workspace)
    monkeypatch.setenv("XDG_DATA_HOME", str(user_data))
    monkeypatch.setenv("COUNCIL_AUTH_SECRET", "cli-trust-verifier-secret")
    monkeypatch.setenv("COUNCIL_PRINCIPAL_ID", "cli-trust-user")
    monkeypatch.setenv("COUNCIL_PRINCIPAL_SCOPES", FULL_SCOPES)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    return workspace, user_data / "council-agent" / "trust"


def _grant(
    *,
    action: str = "read_file",
    resource: str = '{"path":"README.md"}',
    scope: str = "read",
) -> tuple[str, object]:
    result = runner.invoke(
        app,
        [
            "trust",
            "grant",
            action,
            resource,
            "--scope",
            scope,
        ],
    )
    match = UUID_PATTERN.search(result.output)
    assert result.exit_code == 0, result.output
    assert match is not None, result.output
    return match.group(0), result


def test_cli_grant_list_revoke_across_invocations_without_provider_key(
    trust_cli_environment: tuple[Path, Path],
) -> None:
    _workspace, store_root = trust_cli_environment
    grant_id, created = _grant()

    assert "Trust Grant Created" in created.output
    assert "store only" in created.output
    assert "Trust Tier is not enabled" in created.output
    assert store_root.is_dir()
    assert (store_root / "grants.json").is_file()

    listed = runner.invoke(app, ["trust", "list"])
    assert listed.exit_code == 0, listed.output
    assert "read_file" in listed.output
    assert "README.md" in listed.output
    assert "active" in listed.output

    revoked = runner.invoke(app, ["trust", "revoke", grant_id])
    assert revoked.exit_code == 0, revoked.output
    assert "Trust Grant Revoked" in revoked.output
    assert "immediately" in revoked.output

    active = runner.invoke(app, ["trust", "list"])
    assert active.exit_code == 0, active.output
    assert "No active trust grants" in active.output

    history = runner.invoke(app, ["trust", "list", "--all"])
    assert history.exit_code == 0, history.output
    assert "revoked" in history.output
    assert "read_file" in history.output


def test_cli_missing_verifier_fails_without_creating_store(
    trust_cli_environment: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _workspace, store_root = trust_cli_environment
    monkeypatch.delenv("COUNCIL_AUTH_SECRET")
    (Path.cwd() / "council.policy.yaml").write_text(
        "schema_version: 1\ngrant: '*'\n",
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "trust",
            "grant",
            "read_file",
            '{"path":"policy-cannot-grant.txt"}',
            "--scope",
            "read",
        ],
    )

    assert result.exit_code == 1
    assert "trust_authentication_missing" in result.output
    assert not store_root.exists()


def test_cli_scope_and_input_failures_are_nonzero_and_do_not_create_grants(
    trust_cli_environment: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _workspace, store_root = trust_cli_environment
    invalid_json = runner.invoke(
        app,
        ["trust", "grant", "read_file", "{", "--scope", "read"],
    )
    naive_expiry = runner.invoke(
        app,
        [
            "trust",
            "grant",
            "read_file",
            '{"path":"a"}',
            "--scope",
            "read",
            "--expires-at",
            "2026-08-12T00:00:00",
        ],
    )
    unknown_action = runner.invoke(
        app,
        ["trust", "grant", "unknown", '{"path":"a"}', "--scope", "read"],
    )
    monkeypatch.setenv("COUNCIL_PRINCIPAL_SCOPES", "read")
    insufficient = runner.invoke(
        app,
        ["trust", "grant", "read_file", '{"path":"a"}', "--scope", "read"],
    )

    assert invalid_json.exit_code == 1
    assert naive_expiry.exit_code == 1
    assert unknown_action.exit_code == 1
    assert insufficient.exit_code == 1
    assert "trust_scope_insufficient" in insufficient.output
    assert not (store_root / "grants.json").exists()

    read_list = runner.invoke(app, ["trust", "list"])
    assert read_list.exit_code == 0, read_list.output
    assert "No active trust grants" in read_list.output


def test_cli_rejects_corrupt_schema_and_unsafe_permissions(
    trust_cli_environment: tuple[Path, Path],
) -> None:
    _workspace, store_root = trust_cli_environment
    grant_id, _created = _grant()
    state_path = store_root / "grants.json"
    original = json.loads(state_path.read_text(encoding="utf-8"))
    original["schema_version"] = 2
    state_path.write_text(json.dumps(original) + "\n", encoding="utf-8")
    state_path.chmod(0o600)

    corrupt = runner.invoke(app, ["trust", "list"])
    assert corrupt.exit_code == 1
    assert "trust_store_invalid_schema" in corrupt.output
    assert grant_id in state_path.read_text(encoding="utf-8")

    original["schema_version"] = 1
    state_path.write_text(json.dumps(original) + "\n", encoding="utf-8")
    state_path.chmod(0o600)
    store_root.chmod(0o755)
    permissions = runner.invoke(app, ["trust", "list"])
    assert permissions.exit_code == 1
    assert "trust_store_permissions_invalid" in permissions.output
    assert grant_id in state_path.read_text(encoding="utf-8")


def test_cli_audit_is_masked_while_operator_output_keeps_revoke_id(
    trust_cli_environment: tuple[Path, Path],
) -> None:
    _workspace, store_root = trust_cli_environment
    raw_resource = "operator-visible-but-audit-masked.txt"
    grant_id, created = _grant(resource=json.dumps({"path": raw_resource}))
    audit_text = (store_root / "audit" / "events.jsonl").read_text(encoding="utf-8")

    assert grant_id in created.output
    assert raw_resource in created.output
    assert grant_id not in audit_text
    assert raw_resource not in audit_text
    assert "cli-trust-user" not in audit_text
    assert "cli-trust-verifier-secret" not in audit_text
    assert "sha256:" in audit_text


def test_trust_cli_exposes_no_tier_or_confirmation_elevation_options(
    trust_cli_environment: tuple[Path, Path],
) -> None:
    help_result = runner.invoke(app, ["trust", "--help"])
    tier = runner.invoke(app, ["trust", "list", "--trust-tier", "2"])
    yes = runner.invoke(app, ["trust", "list", "--yes"])

    assert help_result.exit_code == 0
    assert "not Trust Tier" in help_result.output
    assert "--trust-tier" not in help_result.output
    assert "--yes" not in help_result.output
    assert tier.exit_code != 0
    assert yes.exit_code != 0


def test_stored_grant_does_not_change_product_tool_scope_decision(
    trust_cli_environment: tuple[Path, Path],
) -> None:
    workspace, _store_root = trust_cli_environment
    _grant(
        action="write_file",
        resource='{"path":"runtime.txt"}',
        scope="filesystem:mutate",
    )
    narrowed = Principal(
        principal_id="cli-trust-user",
        kind=PrincipalKind.LOCAL_USER,
        issuer="council.cli.local",
        scopes=frozenset({PrincipalScope.READ}),
    )
    context = SecurityContext.create(
        workspace,
        request_id="grant-not-runtime",
        tracker=ToolCallTracker(max_tool_calls=10),
        principal=narrowed,
    )

    with without_security_context():
        with security_context(context):
            result = write_file("runtime.txt", "must-not-write")

    assert result.success is False
    assert result.metadata["rejection_reason"] == "scope_insufficient"
    assert not (workspace / "runtime.txt").exists()
