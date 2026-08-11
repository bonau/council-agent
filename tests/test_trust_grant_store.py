"""Core tests for the user-owned persistent trust grant repository."""

from __future__ import annotations

import json
import multiprocessing
import os
import stat
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

import council_agent.security.trust_grants as trust_grants
from council_agent.security.principal import (
    Principal,
    PrincipalKind,
    PrincipalScope,
    full_scope_principal,
)
from council_agent.security.trust_grants import (
    TRUST_DIRECTORY_MODE,
    TRUST_FILE_MODE,
    GrantLookupReason,
    TrustGrant,
    TrustStoreDocument,
    TrustStoreError,
    TrustStoreReason,
    _TrustGrantRepository,
    build_trust_grant,
    canonical_resource_json,
    default_trust_store_root,
    validate_trust_store_file,
)

NOW = datetime(2026, 8, 11, 19, 30, tzinfo=timezone.utc)


@dataclass
class MutableClock:
    value: datetime = NOW

    def __call__(self) -> datetime:
        return self.value


@pytest.fixture
def store_paths(tmp_path: Path) -> tuple[Path, Path]:
    workspace = tmp_path / "workspace"
    user_data = tmp_path / "user-data"
    workspace.mkdir(mode=0o700)
    user_data.mkdir(mode=0o700)
    return workspace, user_data / "trust"


@pytest.fixture
def principal() -> Principal:
    return full_scope_principal("grant-store-user", issuer="pytest")


@pytest.fixture
def repository(
    store_paths: tuple[Path, Path],
) -> _TrustGrantRepository:
    workspace, root = store_paths
    return _TrustGrantRepository(root, workspace, clock=lambda: NOW)


def _grant(
    principal: Principal,
    *,
    resource: dict[str, Any] | None = None,
    scopes: tuple[PrincipalScope, ...] = (PrincipalScope.READ,),
    created_at: datetime = NOW,
    expires_at: datetime | None = None,
) -> TrustGrant:
    return build_trust_grant(
        principal,
        "read_file",
        resource or {"path": "notes.txt", "encoding": "utf-8"},
        scopes,
        created_at=created_at,
        expires_at=expires_at,
    )


def _process_add(
    root: str,
    workspace: str,
    principal_id: str,
    path: str,
) -> None:
    actor = full_scope_principal(principal_id, issuer="multiprocessing-test")
    repository = _TrustGrantRepository(root, workspace, clock=lambda: NOW)
    repository.add(
        build_trust_grant(
            actor,
            "read_file",
            {"path": path},
            [PrincipalScope.READ],
            created_at=NOW,
        )
    )


def test_build_grant_has_exact_canonical_self_binding(
    principal: Principal,
) -> None:
    first = _grant(
        principal,
        resource={"encoding": "utf-8", "path": "notes.txt"},
    )
    second_resource = {"path": "notes.txt", "encoding": "utf-8"}

    assert first.principal_ref == principal.audit_ref
    assert first.created_by_ref == principal.audit_ref
    assert first.principal_kind is PrincipalKind.LOCAL_USER
    assert first.created_by_kind is PrincipalKind.LOCAL_USER
    assert first.action == "read_file"
    assert first.scopes == (PrincipalScope.READ,)
    assert first.canonical_resource == canonical_resource_json(second_resource)
    assert first.created_at == NOW
    assert first.expires_at is None
    assert first.revoked_at is None
    assert first.grant_ref.startswith("sha256:")


@pytest.mark.parametrize(
    ("action", "resource", "scopes", "message"),
    [
        ("unknown", {"path": "a"}, (PrincipalScope.READ,), "not recognized"),
        ("read_file", ["a"], (PrincipalScope.READ,), "JSON object"),
        ("read_file", {"path": "*"}, (PrincipalScope.READ,), "wildcard"),
        ("read_file", {"value": float("nan")}, (PrincipalScope.READ,), "finite"),
        ("read_file", {"path": "a"}, ("unknown",), "unknown scope"),
        ("read_file", {"path": "a"}, (), "non-empty"),
    ],
)
def test_build_grant_rejects_non_exact_authority(
    principal: Principal,
    action: str,
    resource: Any,
    scopes: tuple[Any, ...],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        build_trust_grant(
            principal,
            action,
            resource,
            scopes,
            created_at=NOW,
        )


def test_build_grant_cannot_expand_current_scope() -> None:
    read_only = Principal(
        principal_id="read-only",
        kind=PrincipalKind.LOCAL_USER,
        issuer="pytest",
        scopes=frozenset({PrincipalScope.READ}),
    )

    with pytest.raises(ValueError, match="cannot exceed"):
        build_trust_grant(
            read_only,
            "write_file",
            {"path": "out.txt"},
            [PrincipalScope.FILESYSTEM_MUTATE],
            created_at=NOW,
        )


def test_grant_timestamps_must_be_aware_and_ordered(
    principal: Principal,
) -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        _grant(principal, created_at=NOW.replace(tzinfo=None))
    with pytest.raises(ValidationError, match="expiry"):
        _grant(principal, expires_at=NOW)


def test_document_rejects_duplicate_ids_and_overlapping_bindings(
    principal: Principal,
) -> None:
    first = _grant(principal)
    duplicate_id = _grant(
        principal,
        resource={"path": "other.txt"},
    ).model_copy(update={"grant_id": first.grant_id})
    overlapping = _grant(principal)

    with pytest.raises(ValidationError, match="duplicate grant IDs"):
        TrustStoreDocument(revision=1, grants=(first, duplicate_id))
    with pytest.raises(ValidationError, match="conflicting grant bindings"):
        TrustStoreDocument(revision=1, grants=(first, overlapping))

    expired = _grant(principal, expires_at=NOW + timedelta(seconds=1))
    replacement = _grant(
        principal,
        created_at=NOW + timedelta(seconds=1),
    )
    accepted = TrustStoreDocument(revision=2, grants=(expired, replacement))
    assert len(accepted.grants) == 2


def test_repository_creates_user_only_atomic_state_and_reads_it(
    repository: _TrustGrantRepository,
    principal: Principal,
) -> None:
    stored = repository.add(_grant(principal))
    reopened = _TrustGrantRepository(
        repository.root,
        repository.workspace_root,
        clock=lambda: NOW,
    ).read_document()

    assert stored == reopened
    assert stored.revision == 1
    assert stat.S_IMODE(repository.root.stat().st_mode) == TRUST_DIRECTORY_MODE
    assert stat.S_IMODE(repository.state_path.stat().st_mode) == TRUST_FILE_MODE
    assert stat.S_IMODE(repository.lock_path.stat().st_mode) == TRUST_FILE_MODE
    raw = repository.state_path.read_text(encoding="utf-8")
    assert raw.endswith("\n")
    assert json.loads(raw)["schema_version"] == 1
    assert not list(repository.root.glob(".grants.*.tmp"))


def test_lookup_is_exact_and_respects_current_and_grant_scopes(
    repository: _TrustGrantRepository,
    principal: Principal,
) -> None:
    repository.add(_grant(principal))

    allowed = repository.lookup(
        principal,
        "read_file",
        {"path": "notes.txt", "encoding": "utf-8"},
        [PrincipalScope.READ],
        now=NOW,
    )
    wrong_resource = repository.lookup(
        principal,
        "read_file",
        {"path": "different.txt", "encoding": "utf-8"},
        [PrincipalScope.READ],
        now=NOW,
    )
    grant_scope_missing = repository.lookup(
        principal,
        "read_file",
        {"encoding": "utf-8", "path": "notes.txt"},
        [PrincipalScope.FILESYSTEM_MUTATE],
        now=NOW,
    )
    narrowed = Principal(
        principal_id=principal.principal_id,
        kind=principal.kind,
        issuer=principal.issuer,
        scopes=frozenset(),
    )
    current_scope_missing = repository.lookup(
        narrowed,
        "read_file",
        {"encoding": "utf-8", "path": "notes.txt"},
        [PrincipalScope.READ],
        now=NOW,
    )

    assert allowed.allowed is True
    assert allowed.reason is GrantLookupReason.ALLOWED
    assert allowed.grant_ref is not None
    assert wrong_resource.reason is GrantLookupReason.NOT_FOUND
    assert grant_scope_missing.reason is GrantLookupReason.GRANT_SCOPE_INSUFFICIENT
    assert (
        current_scope_missing.reason
        is GrantLookupReason.PRINCIPAL_SCOPE_INSUFFICIENT
    )


def test_expiry_and_clock_rollback_fail_closed(
    store_paths: tuple[Path, Path],
    principal: Principal,
) -> None:
    workspace, root = store_paths
    clock = MutableClock()
    repository = _TrustGrantRepository(root, workspace, clock=clock)
    repository.add(_grant(principal, expires_at=NOW + timedelta(seconds=5)))
    clock.value += timedelta(seconds=5)

    expired = repository.lookup(
        principal,
        "read_file",
        {"path": "notes.txt", "encoding": "utf-8"},
        [PrincipalScope.READ],
    )
    assert expired.reason is GrantLookupReason.EXPIRED
    assert repository.active_grants(principal.audit_ref) == ()

    clock.value = NOW - timedelta(seconds=1)
    with pytest.raises(TrustStoreError) as error:
        repository.read_document()
    assert error.value.reason is TrustStoreReason.CLOCK_INVALID


def test_revoke_is_immediate_and_persists_across_restart(
    repository: _TrustGrantRepository,
    principal: Principal,
) -> None:
    grant = _grant(principal)
    repository.add(grant)
    repository.revoke(
        grant.grant_id,
        principal.audit_ref,
        revoked_at=NOW,
    )

    decision = repository.lookup(
        principal,
        "read_file",
        {"encoding": "utf-8", "path": "notes.txt"},
        [PrincipalScope.READ],
        now=NOW,
    )
    reopened = _TrustGrantRepository(
        repository.root,
        repository.workspace_root,
        clock=lambda: NOW,
    )

    assert decision.reason is GrantLookupReason.REVOKED
    assert reopened.active_grants(principal.audit_ref, now=NOW) == ()
    persisted = reopened.read_document().grants[0]
    assert persisted.revoked_at == NOW
    assert persisted.revoked_by_ref == principal.audit_ref


@pytest.mark.parametrize(
    ("payload", "reason"),
    [
        ("{", TrustStoreReason.CORRUPT),
        (
            json.dumps({"schema_version": 2, "revision": 0, "grants": []}),
            TrustStoreReason.INVALID_SCHEMA,
        ),
        (
            json.dumps(
                {
                    "schema_version": 1,
                    "revision": 0,
                    "grants": [],
                    "unknown": True,
                }
            ),
            TrustStoreReason.CORRUPT,
        ),
    ],
)
def test_corrupt_unknown_or_future_store_is_not_partially_adopted(
    repository: _TrustGrantRepository,
    payload: str,
    reason: TrustStoreReason,
) -> None:
    repository.read_document()
    repository.state_path.write_text(payload, encoding="utf-8")
    repository.state_path.chmod(TRUST_FILE_MODE)

    with pytest.raises(TrustStoreError) as error:
        repository.read_document()
    assert error.value.reason is reason


def test_persisted_duplicate_and_conflict_invalidate_whole_store(
    repository: _TrustGrantRepository,
    principal: Principal,
) -> None:
    grant = _grant(principal)
    payload = {
        "schema_version": 1,
        "revision": 2,
        "grants": [
            grant.model_dump(mode="json"),
            grant.model_dump(mode="json"),
        ],
    }
    repository.read_document()
    repository.state_path.write_text(
        json.dumps(payload) + "\n",
        encoding="utf-8",
    )
    repository.state_path.chmod(TRUST_FILE_MODE)

    with pytest.raises(TrustStoreError) as error:
        repository.read_document()
    assert error.value.reason is TrustStoreReason.CORRUPT


def test_workspace_overlap_fails_before_creating_state(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir(mode=0o700)
    root = workspace / "trust"
    repository = _TrustGrantRepository(root, workspace, clock=lambda: NOW)

    with pytest.raises(TrustStoreError) as error:
        repository.read_document()

    assert error.value.reason is TrustStoreReason.WORKSPACE_OVERLAP
    assert not root.exists()


def test_unsafe_permissions_owner_and_symlink_fail_closed(
    store_paths: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace, root = store_paths
    root.mkdir(mode=0o700)
    root.chmod(0o755)
    with pytest.raises(TrustStoreError) as permissions:
        _TrustGrantRepository(root, workspace).read_document()
    assert permissions.value.reason is TrustStoreReason.PERMISSIONS
    assert not (root / "grants.json").exists()

    root.chmod(0o700)
    real_uid = os.getuid()
    with monkeypatch.context() as context:
        context.setattr(trust_grants.os, "getuid", lambda: real_uid + 1)
        with pytest.raises(TrustStoreError) as ownership:
            _TrustGrantRepository(root, workspace).read_document()
    assert ownership.value.reason is TrustStoreReason.OWNERSHIP

    target = root.parent / "actual"
    target.mkdir(mode=0o700)
    linked = root.parent / "linked"
    linked.symlink_to(target, target_is_directory=True)
    with pytest.raises(TrustStoreError) as symlink:
        _TrustGrantRepository(linked, workspace).read_document()
    assert symlink.value.reason is TrustStoreReason.UNSAFE_PATH


@pytest.mark.parametrize("failure_point", ["write", "replace"])
def test_failed_atomic_update_preserves_previous_complete_document(
    repository: _TrustGrantRepository,
    principal: Principal,
    monkeypatch: pytest.MonkeyPatch,
    failure_point: str,
) -> None:
    first = _grant(principal)
    repository.add(first)
    original = repository.state_path.read_bytes()
    second = _grant(principal, resource={"path": "second.txt"})

    with monkeypatch.context() as context:
        if failure_point == "replace":
            context.setattr(
                trust_grants.os,
                "replace",
                lambda *args, **kwargs: (_ for _ in ()).throw(OSError("replace")),
            )
        else:
            real_write = trust_grants.os.write
            writes = 0

            def fail_write(descriptor: int, data: bytes) -> int:
                nonlocal writes
                writes += 1
                if writes == 1:
                    partial = max(1, len(data) // 3)
                    real_write(descriptor, data[:partial])
                    raise OSError("write")
                return real_write(descriptor, data)

            context.setattr(trust_grants.os, "write", fail_write)
        with pytest.raises(TrustStoreError) as error:
            repository.add(second)
        assert error.value.reason is TrustStoreReason.IO_FAILURE

    assert repository.state_path.read_bytes() == original
    assert repository.read_document().grants == (first,)
    assert not list(repository.root.glob(".grants.*.tmp"))


def test_concurrent_processes_serialize_without_lost_updates(
    repository: _TrustGrantRepository,
) -> None:
    repository.read_document()
    context = multiprocessing.get_context("spawn")
    processes = [
        context.Process(
            target=_process_add,
            args=(
                str(repository.root),
                str(repository.workspace_root),
                f"process-{index}",
                f"file-{index}.txt",
            ),
        )
        for index in range(2)
    ]

    for process in processes:
        process.start()
    for process in processes:
        process.join(timeout=15)
        assert process.exitcode == 0

    document = repository.read_document()
    assert document.revision == 2
    assert {grant.resource["path"] for grant in document.grants} == {
        "file-0.txt",
        "file-1.txt",
    }


def test_offline_validation_never_repairs_or_changes_input(
    repository: _TrustGrantRepository,
    principal: Principal,
    tmp_path: Path,
) -> None:
    repository.add(_grant(principal))
    backup_root = tmp_path / "backup"
    backup_root.mkdir(mode=0o700)
    backup = backup_root / "grants.json"
    backup.write_bytes(repository.state_path.read_bytes())
    backup.chmod(0o600)
    before = backup.read_bytes()

    validated = validate_trust_store_file(backup, repository.workspace_root)
    assert validated.revision == 1
    assert backup.read_bytes() == before

    backup.write_text('{"schema_version":0}', encoding="utf-8")
    backup.chmod(0o600)
    corrupt = backup.read_bytes()
    with pytest.raises(TrustStoreError) as error:
        validate_trust_store_file(backup, repository.workspace_root)
    assert error.value.reason is TrustStoreReason.INVALID_SCHEMA
    assert backup.read_bytes() == corrupt


def test_default_root_uses_only_absolute_host_xdg(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "home"
    absolute_xdg = tmp_path / "xdg"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_DATA_HOME", str(absolute_xdg))
    assert default_trust_store_root() == absolute_xdg / "council-agent" / "trust"

    monkeypatch.setenv("XDG_DATA_HOME", "project-relative")
    assert default_trust_store_root() == (
        home / ".local" / "share" / "council-agent" / "trust"
    )
