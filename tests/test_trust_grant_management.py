"""Authenticated management and masked audit tests for trust grants."""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from pydantic import SecretStr

from council_agent.sandbox.workspace import WorkspaceBoundaryError, WorkspaceGuard
from council_agent.security.audit import load_audit_events_with_integrity
from council_agent.security.authentication import (
    AuthenticationManager,
    ServiceStepUpProvider,
    answer_challenge,
    masked_reference,
)
from council_agent.security.middleware import (
    SecurityContext,
    security_context,
    without_security_context,
)
from council_agent.security.principal import (
    Principal,
    PrincipalKind,
    PrincipalScope,
    full_scope_principal,
)
from council_agent.security.trust_grants import (
    GrantLookupReason,
    TrustGrantStore,
    TrustStoreError,
    TrustStoreReason,
)
from council_agent.tools.filesystem import write_file
from council_agent.tools.tracker import ToolCallTracker

NOW = datetime(2026, 8, 11, 20, 0, tzinfo=timezone.utc)
VERIFIER = SecretStr("trust-management-verifier-must-remain-secret")


@dataclass
class MutableClock:
    value: datetime = NOW

    def __call__(self) -> datetime:
        return self.value


@pytest.fixture
def trust_paths(tmp_path: Path) -> tuple[Path, Path]:
    workspace = tmp_path / "project"
    user_data = tmp_path / "user-owned"
    workspace.mkdir(mode=0o700)
    user_data.mkdir(mode=0o700)
    return workspace, user_data / "trust"


@pytest.fixture
def principal() -> Principal:
    return full_scope_principal(
        "very-secret-principal-identity",
        issuer="pytest.trust",
    )


@pytest.fixture
def store(trust_paths: tuple[Path, Path]) -> TrustGrantStore:
    workspace, root = trust_paths
    return TrustGrantStore(workspace, root=root, clock=lambda: NOW)


def _service_auth(
    store: TrustGrantStore,
    *,
    request_id: str,
    session_id: str,
) -> tuple[AuthenticationManager, ServiceStepUpProvider]:
    return store.service_authentication(
        VERIFIER,
        request_id=request_id,
        session_id=session_id,
    )


def _local_auth(
    clock: MutableClock | None = None,
    *,
    token_ttl: timedelta = timedelta(minutes=5),
) -> tuple[AuthenticationManager, ServiceStepUpProvider]:
    manager = AuthenticationManager(
        VERIFIER,
        clock=clock or (lambda: NOW),
        token_ttl=token_ttl,
    )
    return manager, ServiceStepUpProvider(manager, VERIFIER)


def test_authenticated_grant_list_lookup_revoke_is_persistent_and_audited(
    store: TrustGrantStore,
    principal: Principal,
) -> None:
    manager, provider = _service_auth(
        store,
        request_id="request-lifecycle",
        session_id="session-lifecycle",
    )
    grant = store.grant(
        principal,
        "read_file",
        {"path": "very-sensitive-resource.txt"},
        [PrincipalScope.READ],
        session_id="session-lifecycle",
        request_id="request-grant",
        authentication_manager=manager,
        step_up_provider=provider,
    )
    listed = store.list(
        principal,
        session_id="session-lifecycle",
        request_id="request-list",
        authentication_manager=manager,
        step_up_provider=provider,
    )
    allowed = store.lookup(
        principal,
        "read_file",
        {"path": "very-sensitive-resource.txt"},
        [PrincipalScope.READ],
        session_id="session-lookup",
        request_id="request-lookup",
    )
    revoked = store.revoke(
        principal,
        grant.grant_id,
        session_id="session-lifecycle",
        request_id="request-revoke",
        authentication_manager=manager,
        step_up_provider=provider,
    )
    after_revoke = store.lookup(
        principal,
        "read_file",
        {"path": "very-sensitive-resource.txt"},
        [PrincipalScope.READ],
        session_id="session-lookup",
        request_id="request-after-revoke",
    )
    reopened = TrustGrantStore(
        store.workspace_root,
        root=store.root,
        clock=lambda: NOW,
    )
    reopened_manager, reopened_provider = _service_auth(
        reopened,
        request_id="request-reopened",
        session_id="session-reopened",
    )
    reopened_active = reopened.list(
        principal,
        session_id="session-reopened",
        request_id="request-reopened-list",
        authentication_manager=reopened_manager,
        step_up_provider=reopened_provider,
    )

    assert listed == (grant,)
    assert allowed.allowed is True
    assert revoked.revoked_at == NOW
    assert after_revoke.reason is GrantLookupReason.REVOKED
    assert reopened_active == ()

    events, integrity = load_audit_events_with_integrity(store.audit_path)
    assert integrity.status == "verified"
    assert any(event.tool == "session_auth" for event in events)
    assert any(
        event.metadata.get("trust_grant", {}).get("reason")
        == "trust_grant_revoked"
        for event in events
    )

    audit_text = store.audit_path.read_text(encoding="utf-8")
    for secret in (
        VERIFIER.get_secret_value(),
        principal.principal_id,
        "very-sensitive-resource.txt",
        grant.grant_id,
    ):
        assert secret not in audit_text
    assert grant.grant_ref in audit_text
    assert principal.audit_ref in audit_text


def test_missing_authentication_and_insufficient_scope_do_not_create_grant_state(
    store: TrustGrantStore,
    principal: Principal,
) -> None:
    with pytest.raises(TrustStoreError) as missing:
        store.grant(
            principal,
            "read_file",
            {"path": "missing-auth.txt"},
            [PrincipalScope.READ],
            session_id="session-missing",
            request_id="request-missing",
            authentication_manager=None,
            step_up_provider=None,
        )
    assert missing.value.reason is TrustStoreReason.AUTHENTICATION_MISSING
    assert not store.state_path.exists()

    read_only = Principal(
        principal_id="read-only-manager",
        kind=PrincipalKind.LOCAL_USER,
        issuer="pytest.trust",
        scopes=frozenset({PrincipalScope.READ}),
    )
    manager, provider = _local_auth()
    with pytest.raises(TrustStoreError) as scope:
        store.grant(
            read_only,
            "read_file",
            {"path": "scope.txt"},
            [PrincipalScope.READ],
            session_id="session-scope",
            request_id="request-scope",
            authentication_manager=manager,
            step_up_provider=provider,
        )
    assert scope.value.reason is TrustStoreReason.SCOPE_INSUFFICIENT
    assert not store.state_path.exists()

    listed = store.list(
        read_only,
        session_id="session-read-list",
        request_id="request-read-list",
        authentication_manager=manager,
        step_up_provider=provider,
    )
    assert listed == ()


def test_authentication_is_bound_to_exact_operation_and_arguments(
    store: TrustGrantStore,
    principal: Principal,
) -> None:
    manager = AuthenticationManager(VERIFIER, clock=lambda: NOW)

    def wrong_operation_provider(requested: object) -> object:
        assert hasattr(requested, "action_ref")
        wrong = replace(requested, action_ref=masked_reference("different-operation"))
        issue = manager.issue_challenge(wrong)
        assert issue.challenge is not None
        completed = manager.complete_challenge(
            issue.challenge,
            answer_challenge(issue.challenge, VERIFIER),
        )
        return completed.token

    with pytest.raises(TrustStoreError) as mismatch:
        store.grant(
            principal,
            "read_file",
            {"path": "exact.txt"},
            [PrincipalScope.READ],
            session_id="session-exact",
            request_id="request-exact",
            authentication_manager=manager,
            step_up_provider=wrong_operation_provider,
        )

    assert mismatch.value.reason is TrustStoreReason.AUTHENTICATION_DENIED
    assert not store.state_path.exists()


def test_replay_expiry_and_revoked_authentication_fail_before_mutation(
    trust_paths: tuple[Path, Path],
    principal: Principal,
) -> None:
    workspace, root = trust_paths
    clock = MutableClock()
    store = TrustGrantStore(workspace, root=root, clock=clock)

    replay_manager = AuthenticationManager(VERIFIER, clock=clock)
    minted: list[object] = []

    def replay_provider(binding: object) -> object:
        if not minted:
            service = ServiceStepUpProvider(replay_manager, VERIFIER)
            minted.append(service(binding))
        return minted[0]

    first = store.list(
        principal,
        session_id="session-replay",
        request_id="request-replay-first",
        authentication_manager=replay_manager,
        step_up_provider=replay_provider,
    )
    assert first == ()
    with pytest.raises(TrustStoreError) as replay:
        store.list(
            principal,
            session_id="session-replay",
            request_id="request-replay-second",
            authentication_manager=replay_manager,
            step_up_provider=replay_provider,
        )
    assert replay.value.reason is TrustStoreReason.AUTHENTICATION_DENIED

    expiry_manager = AuthenticationManager(
        VERIFIER,
        clock=clock,
        token_ttl=timedelta(seconds=1),
    )

    def expired_provider(binding: object) -> object:
        token = ServiceStepUpProvider(expiry_manager, VERIFIER)(binding)
        clock.value += timedelta(seconds=1)
        return token

    with pytest.raises(TrustStoreError) as expired:
        store.grant(
            principal,
            "read_file",
            {"path": "expired.txt"},
            [PrincipalScope.READ],
            session_id="session-expired",
            request_id="request-expired",
            authentication_manager=expiry_manager,
            step_up_provider=expired_provider,
        )
    assert expired.value.reason is TrustStoreReason.AUTHENTICATION_DENIED

    revoked_manager, revoked_provider = _local_auth(clock)
    revoked_manager.revoke()
    with pytest.raises(TrustStoreError) as revoked:
        store.grant(
            principal,
            "read_file",
            {"path": "revoked.txt"},
            [PrincipalScope.READ],
            session_id="session-revoked",
            request_id="request-revoked",
            authentication_manager=revoked_manager,
            step_up_provider=revoked_provider,
        )
    assert revoked.value.reason is TrustStoreReason.AUTHENTICATION_DENIED
    assert not store.state_path.exists()


def test_principal_can_list_only_own_grants_and_cannot_revoke_another(
    store: TrustGrantStore,
    principal: Principal,
) -> None:
    other = full_scope_principal("other-principal", issuer="pytest.trust")
    first_manager, first_provider = _local_auth()
    first = store.grant(
        principal,
        "read_file",
        {"path": "first.txt"},
        [PrincipalScope.READ],
        session_id="session-first",
        request_id="request-first",
        authentication_manager=first_manager,
        step_up_provider=first_provider,
    )
    other_manager, other_provider = _local_auth()
    other_grant = store.grant(
        other,
        "read_file",
        {"path": "other.txt"},
        [PrincipalScope.READ],
        session_id="session-other",
        request_id="request-other",
        authentication_manager=other_manager,
        step_up_provider=other_provider,
    )

    listed = store.list(
        principal,
        session_id="session-first-list",
        request_id="request-first-list",
        authentication_manager=first_manager,
        step_up_provider=first_provider,
    )
    assert listed == (first,)
    assert other_grant not in listed

    with pytest.raises(TrustStoreError) as mismatch:
        store.revoke(
            other,
            first.grant_id,
            session_id="session-other-revoke",
            request_id="request-other-revoke",
            authentication_manager=other_manager,
            step_up_provider=other_provider,
        )
    assert mismatch.value.reason is TrustStoreReason.PRINCIPAL_MISMATCH

    still_active = store.lookup(
        principal,
        "read_file",
        {"path": "first.txt"},
        [PrincipalScope.READ],
        session_id="session-still-active",
        request_id="request-still-active",
    )
    assert still_active.allowed is True


def test_project_policy_and_agent_workspace_write_cannot_create_grants(
    store: TrustGrantStore,
    principal: Principal,
    trust_paths: tuple[Path, Path],
) -> None:
    workspace, _root = trust_paths
    (workspace / "council.policy.yaml").write_text(
        "schema_version: 1\ngrant: '*'\n",
        encoding="utf-8",
    )
    with pytest.raises(TrustStoreError) as denied:
        store.grant(
            principal,
            "read_file",
            {"path": "policy.txt"},
            [PrincipalScope.READ],
            session_id="session-policy",
            request_id="request-policy",
            authentication_manager=None,
            step_up_provider=None,
        )
    assert denied.value.reason is TrustStoreReason.AUTHENTICATION_MISSING
    assert not store.state_path.exists()

    context = SecurityContext.create(
        workspace,
        request_id="workspace-write-bypass",
        tracker=ToolCallTracker(max_tool_calls=10),
        principal=principal,
    )
    with without_security_context():
        with security_context(context):
            result = write_file(str(store.state_path), '{"schema_version":1}')

    assert result.success is False
    assert result.metadata["rejection_reason"] == "workspace_boundary"
    assert not store.state_path.exists()
    with pytest.raises(WorkspaceBoundaryError):
        WorkspaceGuard(workspace).resolve(store.state_path)


def test_corrupt_store_and_audit_fail_closed_without_new_grant(
    store: TrustGrantStore,
    principal: Principal,
) -> None:
    manager, provider = _local_auth()
    first = store.grant(
        principal,
        "read_file",
        {"path": "first.txt"},
        [PrincipalScope.READ],
        session_id="session-first",
        request_id="request-first",
        authentication_manager=manager,
        step_up_provider=provider,
    )
    original_state = store.state_path.read_bytes()

    audit_text = store.audit_path.read_text(encoding="utf-8")
    store.audit_path.write_text(audit_text + "not-json\n", encoding="utf-8")
    store.audit_path.chmod(0o600)
    with pytest.raises(TrustStoreError) as audit:
        store.grant(
            principal,
            "read_file",
            {"path": "second.txt"},
            [PrincipalScope.READ],
            session_id="session-audit-failure",
            request_id="request-audit-failure",
            authentication_manager=manager,
            step_up_provider=provider,
        )
    assert audit.value.reason is TrustStoreReason.AUDIT_FAILURE
    assert store.state_path.read_bytes() == original_state

    store.audit_path.write_text(audit_text, encoding="utf-8")
    store.audit_path.chmod(0o600)
    state = json.loads(original_state)
    state["schema_version"] = 2
    store.state_path.write_text(json.dumps(state) + "\n", encoding="utf-8")
    store.state_path.chmod(0o600)
    fresh_manager, fresh_provider = _local_auth()
    with pytest.raises(TrustStoreError) as schema:
        store.list(
            principal,
            session_id="session-schema",
            request_id="request-schema",
            authentication_manager=fresh_manager,
            step_up_provider=fresh_provider,
        )
    assert schema.value.reason is TrustStoreReason.INVALID_SCHEMA
    assert first.grant_id in store.state_path.read_text(encoding="utf-8")
