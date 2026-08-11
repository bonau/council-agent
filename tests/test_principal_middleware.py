"""Authorization-boundary tests for principal scopes in the dispatcher."""

from __future__ import annotations

import json
from pathlib import Path
from unittest import mock

from council_agent.security import (
    AuditLogger,
    ConfirmMode,
    ConfirmationPolicy,
    CouncilPolicy,
    Principal,
    PrincipalKind,
    PrincipalScope,
    SecurityContext,
    full_scope_principal,
    load_audit_events,
    security_context,
    without_security_context,
)
from council_agent.tools import read_file, run_command, run_tests, write_file


def _principal(
    *scopes: PrincipalScope,
    principal_id: str = "principal:test-user",
) -> Principal:
    return Principal(
        principal_id=principal_id,
        kind=PrincipalKind.LOCAL_USER,
        issuer="pytest",
        scopes=frozenset(scopes),
    )


def test_context_without_principal_denies_and_audits_before_handler(
    tmp_path: Path,
) -> None:
    audit_path = tmp_path / "audit" / "events.jsonl"
    context = SecurityContext.create(
        tmp_path,
        audit_logger=AuditLogger(audit_path),
    )
    target = tmp_path / "blocked.txt"

    with (
        without_security_context(),
        security_context(context),
        mock.patch("council_agent.tools.filesystem._write_file") as handler,
    ):
        result = write_file("blocked.txt", "blocked")

    assert result.success is False
    assert result.metadata["rejection_reason"] == "principal_missing"
    assert result.metadata["authorization"]["scope_decision"] == "deny"
    assert handler.call_count == 0
    assert not target.exists()
    events = load_audit_events(audit_path)
    assert [event.phase for event in events] == ["attempt", "result"]
    assert all(
        event.metadata["authorization"]["reason"] == "principal_missing"
        for event in events
    )


def test_read_only_principal_allows_read_and_denies_mutation_without_prompt(
    tmp_path: Path,
) -> None:
    target = tmp_path / "sentinel.txt"
    target.write_text("unchanged", encoding="utf-8")
    prompts: list[str] = []
    principal = _principal(PrincipalScope.READ)
    context = SecurityContext.create(
        tmp_path,
        principal=principal,
        confirmation=ConfirmationPolicy(
            mode=ConfirmMode.ASK,
            confirm_fn=lambda prompt: prompts.append(prompt) or True,
        ),
    )

    with without_security_context(), security_context(context):
        read_result = read_file("sentinel.txt")
        write_result = write_file("sentinel.txt", "changed")

    assert read_result.success is True
    assert write_result.success is False
    assert write_result.metadata["rejection_reason"] == "scope_insufficient"
    assert write_result.metadata["authorization"]["missing_scopes"] == [
        "filesystem:mutate"
    ]
    assert target.read_text(encoding="utf-8") == "unchanged"
    assert prompts == []
    assert [summary.tool for summary in context.tracker.summaries] == ["read_file"]


def test_scope_tightening_and_revocation_apply_on_next_decision(
    tmp_path: Path,
) -> None:
    target = tmp_path / "item.txt"
    target.write_text("original", encoding="utf-8")
    bound = full_scope_principal("dynamic-user", issuer="pytest")
    state: list[Principal | None] = [bound]
    context = SecurityContext.create(
        tmp_path,
        principal=bound,
        principal_resolver=lambda: state[0],
    )

    with without_security_context(), security_context(context):
        first = write_file("item.txt", "first")
        state[0] = _principal(
            PrincipalScope.READ,
            principal_id="dynamic-user",
        )
        tightened = write_file("item.txt", "second")
        state[0] = None
        revoked = read_file("item.txt")

    assert first.success is True
    assert tightened.metadata["rejection_reason"] == "scope_insufficient"
    assert revoked.metadata["rejection_reason"] == "principal_revoked"
    assert target.read_text(encoding="utf-8") == "first"
    assert len(context.tracker.summaries) == 1


def test_invalid_and_substituted_current_principal_fail_closed(
    tmp_path: Path,
) -> None:
    bound = _principal(PrincipalScope.READ)
    current: list[object] = [object()]
    context = SecurityContext.create(
        tmp_path,
        principal=bound,
        principal_resolver=lambda: current[0],  # type: ignore[arg-type]
    )
    target = tmp_path / "readable.txt"
    target.write_text("content", encoding="utf-8")

    with without_security_context(), security_context(context):
        invalid = read_file("readable.txt")
        current[0] = _principal(
            PrincipalScope.READ,
            principal_id="substitute",
        )
        mismatch = read_file("readable.txt")

    assert invalid.metadata["rejection_reason"] == "principal_invalid"
    assert mismatch.metadata["rejection_reason"] == "principal_mismatch"
    assert context.tracker.summaries == []


def test_scope_denial_precedes_project_policy_confirmation_and_process(
    tmp_path: Path,
) -> None:
    prompts: list[str] = []
    context = SecurityContext.create(
        tmp_path,
        principal=_principal(PrincipalScope.READ),
        policy=CouncilPolicy(
            schema_version=1,
            allowed_commands=["mkdir *"],
        ),
        confirmation=ConfirmationPolicy(
            mode=ConfirmMode.ASK,
            confirm_fn=lambda prompt: prompts.append(prompt) or True,
        ),
    )

    with (
        without_security_context(),
        security_context(context),
        mock.patch("council_agent.tools.shell._authorize_action") as lower_gate,
        mock.patch("council_agent.tools.shell.subprocess.run") as process,
    ):
        result = run_command("mkdir marker")

    assert result.metadata["rejection_reason"] == "scope_insufficient"
    assert result.metadata["authorization"]["missing_scopes"] == [
        "filesystem:mutate",
        "shell",
    ]
    assert lower_gate.call_count == 0
    assert process.call_count == 0
    assert prompts == []
    assert not (tmp_path / "marker").exists()


def test_read_only_run_tests_denial_starts_no_process_or_nested_action(
    tmp_path: Path,
) -> None:
    audit_path = tmp_path / "audit" / "events.jsonl"
    context = SecurityContext.create(
        tmp_path,
        principal=_principal(PrincipalScope.READ),
        audit_logger=AuditLogger(audit_path),
    )
    sentinel = tmp_path / "sentinel.txt"
    sentinel.write_text("unchanged", encoding="utf-8")

    with (
        without_security_context(),
        security_context(context),
        mock.patch("council_agent.tools.shell.subprocess.run") as process,
    ):
        result = run_tests(".")

    assert result.metadata["rejection_reason"] == "scope_insufficient"
    assert result.metadata["authorization"]["missing_scopes"] == [
        "filesystem:mutate",
        "test",
    ]
    assert process.call_count == 0
    assert sentinel.read_text(encoding="utf-8") == "unchanged"
    assert context.tracker.summaries == []
    events = load_audit_events(audit_path)
    assert len(events) == 2
    assert {event.tool for event in events} == {"run_tests"}


def test_audit_masks_raw_principal_and_provider_credential_text(
    tmp_path: Path,
) -> None:
    raw_principal = "sk-or-v1-principal-identity-secret"
    provider_secret = "sk-or-v1-provider-credential-secret"
    principal = _principal(
        PrincipalScope.READ,
        principal_id=raw_principal,
    )
    audit_path = tmp_path / "audit" / "events.jsonl"
    context = SecurityContext.create(
        tmp_path,
        principal=principal,
        audit_logger=AuditLogger(audit_path),
    )
    (tmp_path / "item.txt").write_text("content", encoding="utf-8")

    with without_security_context(), security_context(context):
        result = read_file("item.txt")
        denied = run_command("echo denied")
        injected = __import__(
            "council_agent.security.middleware",
            fromlist=["invoke"],
        ).invoke(
            "read_file",
            path="item.txt",
            provider_api_key=provider_secret,
        )

    raw_audit = audit_path.read_text(encoding="utf-8")
    events = load_audit_events(audit_path)
    first_attempt, first_result = events[:2]
    assert result.success is True
    assert denied.metadata["rejection_reason"] == "scope_insufficient"
    assert injected.success is False
    assert raw_principal not in raw_audit
    assert provider_secret not in raw_audit
    assert first_attempt.metadata["authorization"]["principal_ref"] == (
        principal.audit_ref
    )
    assert first_result.metadata["authorization"]["principal_ref"] == (
        principal.audit_ref
    )
    assert first_result.attempt_event_id == first_attempt.event_id


def test_authorization_metadata_is_json_serializable(tmp_path: Path) -> None:
    principal = _principal(PrincipalScope.READ)
    context = SecurityContext.create(tmp_path, principal=principal)
    (tmp_path / "item.txt").write_text("content", encoding="utf-8")

    with without_security_context(), security_context(context):
        result = read_file("item.txt")

    encoded = json.dumps(result.metadata["authorization"], sort_keys=True)
    assert principal.principal_id not in encoded
    assert '"scope_decision": "allow"' in encoded
