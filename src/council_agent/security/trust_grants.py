"""User-owned, workspace-external persistent trust grant storage."""

from __future__ import annotations

import json
import os
import secrets
import stat
import threading
import uuid
from collections.abc import Callable, Iterable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, TypeAlias

from pydantic import BaseModel, ConfigDict, field_validator, model_validator
from pydantic import SecretStr

from council_agent.security.authentication import (
    AuthenticationBinding,
    AuthenticationManager,
    AuthenticationReason,
    ServiceStepUpProvider,
    StepUpProvider,
    authentication_audit_sink,
    masked_reference,
)
from council_agent.security.audit import (
    DEFAULT_EVENTS_FILENAME,
    AuditLogger,
)
from council_agent.security.principal import (
    Principal,
    PrincipalKind,
    PrincipalScope,
)

TRUST_STORE_SCHEMA_VERSION = 1
TRUST_STATE_FILENAME = "grants.json"
TRUST_LOCK_FILENAME = "grants.lock"
TRUST_AUDIT_DIRECTORY = "audit"
TRUST_DIRECTORY_MODE = 0o700
TRUST_FILE_MODE = 0o600
TRUST_REFERENCE_PREFIX = "sha256:"
TRUST_MANAGEMENT_PURPOSE = "trust-store-management"
TRUST_GRANT_ACTIONS = frozenset(
    {
        "read_file",
        "write_file",
        "list_dir",
        "delete_file",
        "run_command",
        "run_tests",
    }
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


Clock: TypeAlias = Callable[[], datetime]


class TrustStoreReason(str, Enum):
    """Stable fail-closed grant-store result reasons."""

    UNSUPPORTED_PLATFORM = "trust_store_unsupported_platform"
    WORKSPACE_OVERLAP = "trust_store_workspace_overlap"
    UNSAFE_PATH = "trust_store_unsafe_path"
    OWNERSHIP = "trust_store_ownership_invalid"
    PERMISSIONS = "trust_store_permissions_invalid"
    IO_FAILURE = "trust_store_io_failure"
    LOCK_FAILURE = "trust_store_lock_failure"
    INVALID_SCHEMA = "trust_store_invalid_schema"
    CORRUPT = "trust_store_corrupt"
    CONFLICT = "trust_store_conflict"
    INVALID_REQUEST = "trust_grant_invalid_request"
    GRANT_NOT_FOUND = "trust_grant_not_found"
    GRANT_REVOKED = "trust_grant_revoked"
    CLOCK_INVALID = "trust_store_clock_invalid"
    AUTHENTICATION_MISSING = "trust_authentication_missing"
    AUTHENTICATION_DENIED = "trust_authentication_denied"
    SCOPE_INSUFFICIENT = "trust_scope_insufficient"
    PRINCIPAL_MISMATCH = "trust_principal_mismatch"
    AUDIT_FAILURE = "trust_audit_failure"


class TrustStoreError(RuntimeError):
    """A typed error that never includes persisted grant contents."""

    def __init__(self, message: str, reason: TrustStoreReason) -> None:
        super().__init__(message)
        self.reason = reason


class GrantLookupReason(str, Enum):
    """Stable exact-lookup decisions for future policy integration."""

    ALLOWED = "trust_grant_allowed"
    NOT_FOUND = "trust_grant_not_found"
    REVOKED = "trust_grant_revoked"
    EXPIRED = "trust_grant_expired"
    PRINCIPAL_SCOPE_INSUFFICIENT = "trust_principal_scope_insufficient"
    GRANT_SCOPE_INSUFFICIENT = "trust_grant_scope_insufficient"


class TrustOperation(str, Enum):
    """Authenticated trust-store management operations."""

    GRANT = "grant"
    REVOKE = "revoke"
    LIST = "list"


@dataclass(frozen=True)
class GrantLookupDecision:
    """One credential-free exact lookup result."""

    allowed: bool
    reason: GrantLookupReason
    principal_ref: str
    required_scopes: frozenset[PrincipalScope]
    granted_scopes: frozenset[PrincipalScope]
    grant_ref: str | None = None

    def to_metadata(self) -> dict[str, Any]:
        return {
            "grant_decision": "allow" if self.allowed else "deny",
            "reason": self.reason.value,
            "principal_ref": self.principal_ref,
            "required_scopes": sorted(scope.value for scope in self.required_scopes),
            "granted_scopes": sorted(scope.value for scope in self.granted_scopes),
            "grant_ref": self.grant_ref,
        }


def _aware_utc(value: datetime, field_name: str) -> datetime:
    if not isinstance(value, datetime):
        raise ValueError(f"{field_name} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _canonical_resource(value: object) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError("Trust grant resource must be a JSON object")
    try:
        encoded = json.dumps(
            dict(value),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        decoded = json.loads(encoded)
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("Trust grant resource must contain only finite JSON values") from exc
    if not isinstance(decoded, dict):
        raise ValueError("Trust grant resource must be a JSON object")
    if _contains_wildcard_authority(decoded):
        raise ValueError("Trust grant resource cannot contain wildcard authority")
    return decoded


def _contains_wildcard_authority(value: object) -> bool:
    if isinstance(value, str):
        return value.strip() == "*"
    if isinstance(value, list):
        return any(_contains_wildcard_authority(item) for item in value)
    if isinstance(value, dict):
        return any(_contains_wildcard_authority(item) for item in value.values())
    return False


def canonical_resource_json(value: Mapping[str, Any]) -> str:
    """Return the exact canonical JSON representation used for matching."""

    return json.dumps(
        _canonical_resource(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _valid_reference(value: str) -> bool:
    if not value.startswith(TRUST_REFERENCE_PREFIX):
        return False
    digest = value.removeprefix(TRUST_REFERENCE_PREFIX)
    return len(digest) == 32 and all(char in "0123456789abcdef" for char in digest)


class TrustGrant(BaseModel):
    """One exact persistent grant and optional revocation tombstone."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    grant_id: str
    principal_ref: str
    principal_kind: PrincipalKind
    action: str
    resource: dict[str, Any]
    scopes: tuple[PrincipalScope, ...]
    created_by_ref: str
    created_by_kind: PrincipalKind
    created_at: datetime
    expires_at: datetime | None = None
    revoked_at: datetime | None = None
    revoked_by_ref: str | None = None

    @field_validator("grant_id")
    @classmethod
    def _validate_grant_id(cls, value: str) -> str:
        if not isinstance(value, str):
            raise ValueError("grant_id must be a string")
        try:
            parsed = uuid.UUID(value)
        except (ValueError, AttributeError) as exc:
            raise ValueError("grant_id must be a canonical UUID") from exc
        if str(parsed) != value:
            raise ValueError("grant_id must be a canonical UUID")
        return value

    @field_validator("principal_ref", "created_by_ref", "revoked_by_ref")
    @classmethod
    def _validate_reference(cls, value: str | None) -> str | None:
        if value is not None and (not isinstance(value, str) or not _valid_reference(value)):
            raise ValueError("principal references must be masked sha256 references")
        return value

    @field_validator("action")
    @classmethod
    def _validate_action(cls, value: str) -> str:
        if not isinstance(value, str) or value not in TRUST_GRANT_ACTIONS:
            raise ValueError("Trust grant action is not recognized")
        return value

    @field_validator("resource")
    @classmethod
    def _validate_resource(cls, value: object) -> dict[str, Any]:
        return _canonical_resource(value)

    @field_validator("scopes")
    @classmethod
    def _validate_scopes(
        cls,
        value: tuple[PrincipalScope, ...],
    ) -> tuple[PrincipalScope, ...]:
        if not value:
            raise ValueError("Trust grant scopes must be non-empty")
        if any(not isinstance(scope, PrincipalScope) for scope in value):
            raise ValueError("Trust grant contains an unknown scope")
        canonical = tuple(sorted(set(value), key=lambda scope: scope.value))
        if canonical != value:
            raise ValueError("Trust grant scopes must be unique and sorted")
        return value

    @field_validator("created_at", "expires_at", "revoked_at")
    @classmethod
    def _validate_timestamp(
        cls,
        value: datetime | None,
        info: Any,
    ) -> datetime | None:
        if value is None:
            return None
        return _aware_utc(value, info.field_name)

    @model_validator(mode="after")
    def _validate_lifecycle(self) -> TrustGrant:
        if self.expires_at is not None and self.expires_at <= self.created_at:
            raise ValueError("Grant expiry must follow creation")
        if (self.revoked_at is None) != (self.revoked_by_ref is None):
            raise ValueError("Grant revocation time and actor must be present together")
        if self.revoked_at is not None and self.revoked_at < self.created_at:
            raise ValueError("Grant revocation cannot precede creation")
        return self

    @property
    def canonical_resource(self) -> str:
        return canonical_resource_json(self.resource)

    @property
    def target_key(self) -> tuple[str, str, str]:
        return (self.principal_ref, self.action, self.canonical_resource)

    @property
    def grant_ref(self) -> str:
        return masked_reference(self.grant_id)

    def is_active(self, now: datetime) -> bool:
        current = _aware_utc(now, "now")
        return self.revoked_at is None and (
            self.expires_at is None or current < self.expires_at
        )


class TrustStoreDocument(BaseModel):
    """The complete atomic schema-v1 trust state."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: int = TRUST_STORE_SCHEMA_VERSION
    revision: int = 0
    grants: tuple[TrustGrant, ...] = ()

    @field_validator("schema_version", mode="before")
    @classmethod
    def _validate_schema_version(cls, value: object) -> int:
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError("Trust store schema_version must be an integer")
        if value != TRUST_STORE_SCHEMA_VERSION:
            raise ValueError("Trust store schema_version is unsupported")
        return value

    @field_validator("revision", mode="before")
    @classmethod
    def _validate_revision(cls, value: object) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError("Trust store revision must be a non-negative integer")
        return value

    @model_validator(mode="after")
    def _validate_records(self) -> TrustStoreDocument:
        ids: set[str] = set()
        by_target: dict[tuple[str, str, str], list[TrustGrant]] = {}
        for grant in self.grants:
            if grant.grant_id in ids:
                raise ValueError("Trust store contains duplicate grant IDs")
            ids.add(grant.grant_id)
            by_target.setdefault(grant.target_key, []).append(grant)
        for records in by_target.values():
            for index, left in enumerate(records):
                for right in records[index + 1 :]:
                    if _grant_intervals_overlap(left, right):
                        raise ValueError("Trust store contains conflicting grant bindings")
        return self


def _grant_end(grant: TrustGrant) -> datetime | None:
    candidates = [
        timestamp
        for timestamp in (grant.expires_at, grant.revoked_at)
        if timestamp is not None
    ]
    return min(candidates) if candidates else None


def _grant_intervals_overlap(left: TrustGrant, right: TrustGrant) -> bool:
    start = max(left.created_at, right.created_at)
    left_end = _grant_end(left)
    right_end = _grant_end(right)
    ends = [value for value in (left_end, right_end) if value is not None]
    end = min(ends) if ends else None
    return end is None or start < end


def build_trust_grant(
    principal: Principal,
    action: str,
    resource: Mapping[str, Any],
    scopes: Iterable[PrincipalScope | str],
    *,
    created_at: datetime | None = None,
    expires_at: datetime | None = None,
    grant_id: str | None = None,
) -> TrustGrant:
    """Build one exact self-grant without persisting it."""

    if not isinstance(principal, Principal):
        raise ValueError("Trust grant principal is invalid")
    principal.__post_init__()
    parsed_scopes: set[PrincipalScope] = set()
    for scope in scopes:
        try:
            parsed_scopes.add(
                scope if isinstance(scope, PrincipalScope) else PrincipalScope(scope)
            )
        except (TypeError, ValueError) as exc:
            raise ValueError("Trust grant contains an unknown scope") from exc
    if not parsed_scopes:
        raise ValueError("Trust grant scopes must be non-empty")
    if not parsed_scopes.issubset(principal.scopes):
        raise ValueError("Trust grant cannot exceed current principal scopes")
    now = _aware_utc(created_at or _utc_now(), "created_at")
    expiry = None if expires_at is None else _aware_utc(expires_at, "expires_at")
    return TrustGrant(
        grant_id=grant_id or str(uuid.uuid4()),
        principal_ref=principal.audit_ref,
        principal_kind=principal.kind,
        action=action,
        resource=_canonical_resource(resource),
        scopes=tuple(sorted(parsed_scopes, key=lambda item: item.value)),
        created_by_ref=principal.audit_ref,
        created_by_kind=principal.kind,
        created_at=now,
        expires_at=expiry,
    )


def default_trust_store_root() -> Path:
    """Resolve the host-user data root without consulting project settings."""

    configured = os.environ.get("XDG_DATA_HOME")
    if configured:
        candidate = Path(configured).expanduser()
        base = candidate if candidate.is_absolute() else Path.home() / ".local" / "share"
    else:
        base = Path.home() / ".local" / "share"
    return base / "council-agent" / "trust"


_ROOT_LOCKS: dict[Path, threading.RLock] = {}
_ROOT_LOCKS_GUARD = threading.Lock()


class _TrustGrantRepository:
    """Internal persistence layer; authenticated callers wrap this class."""

    def __init__(
        self,
        root: Path | str,
        workspace_root: Path | str,
        *,
        clock: Clock = _utc_now,
    ) -> None:
        self.root = Path(os.path.abspath(os.path.expanduser(str(root))))
        self.workspace_root = Path(workspace_root).expanduser().resolve()
        self._clock = clock

    @property
    def state_path(self) -> Path:
        return self.root / TRUST_STATE_FILENAME

    @property
    def lock_path(self) -> Path:
        return self.root / TRUST_LOCK_FILENAME

    @property
    def audit_path(self) -> Path:
        return self.root / TRUST_AUDIT_DIRECTORY / DEFAULT_EVENTS_FILENAME

    def audit_logger(self) -> AuditLogger:
        """Open the validated user-owned audit sink without weakening its modes."""

        self._ensure_secure_root()
        audit_directory = self.audit_path.parent
        try:
            audit_directory.mkdir(mode=TRUST_DIRECTORY_MODE)
        except FileExistsError:
            pass
        except OSError as exc:
            raise TrustStoreError(
                "Trust audit directory could not be created",
                TrustStoreReason.AUDIT_FAILURE,
            ) from exc
        self._validate_existing_directory(audit_directory, strict=True)
        if Path(os.path.realpath(audit_directory)) != audit_directory:
            raise TrustStoreError(
                "Trust audit path cannot contain symlinks",
                TrustStoreReason.UNSAFE_PATH,
            )

        directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
        directory_flags |= getattr(os, "O_NOFOLLOW", 0)
        try:
            directory_fd = os.open(audit_directory, directory_flags)
        except OSError as exc:
            raise TrustStoreError(
                "Trust audit directory could not be opened safely",
                TrustStoreReason.AUDIT_FAILURE,
            ) from exc
        try:
            self._validate_fd(
                directory_fd,
                directory=True,
                strict_directory=True,
            )
            for name in (
                DEFAULT_EVENTS_FILENAME,
                f"{DEFAULT_EVENTS_FILENAME}.lock",
            ):
                descriptor = os.open(
                    name,
                    os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0),
                    TRUST_FILE_MODE,
                    dir_fd=directory_fd,
                )
                try:
                    self._validate_fd(descriptor, directory=False)
                finally:
                    os.close(descriptor)
        except (OSError, TrustStoreError) as exc:
            if isinstance(exc, TrustStoreError):
                raise
            raise TrustStoreError(
                "Trust audit files could not be opened safely",
                TrustStoreReason.AUDIT_FAILURE,
            ) from exc
        finally:
            os.close(directory_fd)
        return AuditLogger(self.audit_path)

    def read_document(self) -> TrustStoreDocument:
        with self._locked_root() as root_fd:
            document = self._read_locked(root_fd)
            self._validate_clock(document, self._now())
            return document

    def add(self, grant: TrustGrant) -> TrustStoreDocument:
        if not isinstance(grant, TrustGrant):
            raise TypeError("grant must be a TrustGrant")

        def _add(document: TrustStoreDocument) -> TrustStoreDocument:
            now = self._now()
            self._validate_clock(document, now)
            if grant.created_at > now:
                raise TrustStoreError(
                    "Grant creation time is ahead of the trusted clock",
                    TrustStoreReason.CLOCK_INVALID,
                )
            try:
                return TrustStoreDocument(
                    revision=document.revision + 1,
                    grants=(*document.grants, grant),
                )
            except ValueError as exc:
                raise TrustStoreError(
                    "Trust grant conflicts with current state",
                    TrustStoreReason.CONFLICT,
                ) from exc

        return self._mutate(_add)

    def revoke(
        self,
        grant_id: str,
        revoked_by_ref: str,
        *,
        revoked_at: datetime | None = None,
    ) -> TrustStoreDocument:
        when = _aware_utc(revoked_at or self._now(), "revoked_at")
        if not _valid_reference(revoked_by_ref):
            raise ValueError("revoked_by_ref must be a masked sha256 reference")

        def _revoke(document: TrustStoreDocument) -> TrustStoreDocument:
            self._validate_clock(document, when)
            records = list(document.grants)
            for index, grant in enumerate(records):
                if grant.grant_id != grant_id:
                    continue
                if grant.revoked_at is not None:
                    raise TrustStoreError(
                        "Trust grant has already been revoked",
                        TrustStoreReason.GRANT_REVOKED,
                    )
                try:
                    records[index] = TrustGrant.model_validate(
                        {
                            **grant.model_dump(mode="python"),
                            "revoked_at": when,
                            "revoked_by_ref": revoked_by_ref,
                        }
                    )
                    updated = TrustStoreDocument(
                        revision=document.revision + 1,
                        grants=tuple(records),
                    )
                except ValueError as exc:
                    raise TrustStoreError(
                        "Trust grant revocation is invalid",
                        TrustStoreReason.CLOCK_INVALID,
                    ) from exc
                return updated
            raise TrustStoreError(
                "Trust grant does not exist",
                TrustStoreReason.GRANT_NOT_FOUND,
            )

        return self._mutate(_revoke)

    def active_grants(
        self,
        principal_ref: str,
        *,
        now: datetime | None = None,
    ) -> tuple[TrustGrant, ...]:
        current = _aware_utc(now or self._now(), "now")
        document = self.read_document()
        self._validate_clock(document, current)
        return tuple(
            grant
            for grant in document.grants
            if grant.principal_ref == principal_ref and grant.is_active(current)
        )

    def lookup(
        self,
        principal: Principal,
        action: str,
        resource: Mapping[str, Any],
        required_scopes: Iterable[PrincipalScope | str],
        *,
        now: datetime | None = None,
    ) -> GrantLookupDecision:
        principal.__post_init__()
        canonical = canonical_resource_json(resource)
        if action not in TRUST_GRANT_ACTIONS:
            raise ValueError("Trust grant action is not recognized")
        required = _parse_scope_set(required_scopes)
        current = _aware_utc(now or self._now(), "now")
        document = self.read_document()
        self._validate_clock(document, current)
        matches = [
            grant
            for grant in document.grants
            if grant.principal_ref == principal.audit_ref
            and grant.action == action
            and grant.canonical_resource == canonical
        ]
        active = [grant for grant in matches if grant.is_active(current)]
        if not required.issubset(principal.scopes):
            return GrantLookupDecision(
                allowed=False,
                reason=GrantLookupReason.PRINCIPAL_SCOPE_INSUFFICIENT,
                principal_ref=principal.audit_ref,
                required_scopes=required,
                granted_scopes=frozenset(),
            )
        if active:
            grant = active[0]
            granted = frozenset(grant.scopes)
            allowed = required.issubset(granted)
            return GrantLookupDecision(
                allowed=allowed,
                reason=(
                    GrantLookupReason.ALLOWED
                    if allowed
                    else GrantLookupReason.GRANT_SCOPE_INSUFFICIENT
                ),
                principal_ref=principal.audit_ref,
                required_scopes=required,
                granted_scopes=granted,
                grant_ref=grant.grant_ref,
            )
        reason = (
            GrantLookupReason.REVOKED
            if any(grant.revoked_at is not None for grant in matches)
            else GrantLookupReason.EXPIRED
            if matches
            else GrantLookupReason.NOT_FOUND
        )
        return GrantLookupDecision(
            allowed=False,
            reason=reason,
            principal_ref=principal.audit_ref,
            required_scopes=required,
            granted_scopes=frozenset(),
        )

    def _mutate(
        self,
        operation: Callable[[TrustStoreDocument], TrustStoreDocument],
    ) -> TrustStoreDocument:
        with self._locked_root() as root_fd:
            current = self._read_locked(root_fd)
            updated = operation(current)
            self._write_locked(root_fd, updated)
            committed = self._read_locked(root_fd)
            if committed != updated:
                raise TrustStoreError(
                    "Committed trust state did not pass exact validation",
                    TrustStoreReason.IO_FAILURE,
                )
            return committed

    @contextmanager
    def _locked_root(self) -> Iterator[int]:
        self._ensure_secure_root()
        with _ROOT_LOCKS_GUARD:
            local_lock = _ROOT_LOCKS.setdefault(self.root, threading.RLock())
        with local_lock:
            root_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
            root_flags |= getattr(os, "O_NOFOLLOW", 0)
            try:
                root_fd = os.open(self.root, root_flags)
            except OSError as exc:
                raise TrustStoreError(
                    "Trust store root could not be opened safely",
                    TrustStoreReason.IO_FAILURE,
                ) from exc
            lock_fd: int | None = None
            try:
                self._validate_fd(root_fd, directory=True, strict_directory=True)
                lock_flags = os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
                lock_fd = os.open(
                    TRUST_LOCK_FILENAME,
                    lock_flags,
                    TRUST_FILE_MODE,
                    dir_fd=root_fd,
                )
                self._validate_fd(lock_fd, directory=False)
                try:
                    import fcntl
                except ImportError as exc:  # pragma: no cover - non-POSIX
                    raise TrustStoreError(
                        "Secure inter-process locking is unavailable",
                        TrustStoreReason.UNSUPPORTED_PLATFORM,
                    ) from exc
                try:
                    fcntl.flock(lock_fd, fcntl.LOCK_EX)
                except OSError as exc:
                    raise TrustStoreError(
                        "Trust store lock could not be acquired",
                        TrustStoreReason.LOCK_FAILURE,
                    ) from exc
                yield root_fd
            except OSError as exc:
                raise TrustStoreError(
                    "Trust store control file could not be opened safely",
                    TrustStoreReason.IO_FAILURE,
                ) from exc
            finally:
                if lock_fd is not None:
                    try:
                        import fcntl

                        fcntl.flock(lock_fd, fcntl.LOCK_UN)
                    except (ImportError, OSError):
                        pass
                    os.close(lock_fd)
                os.close(root_fd)

    def _ensure_secure_root(self) -> None:
        if os.name != "posix" or not hasattr(os, "getuid"):
            raise TrustStoreError(
                "Trust store ownership checks require a POSIX local-user boundary",
                TrustStoreReason.UNSUPPORTED_PLATFORM,
            )
        if Path(os.path.realpath(self.root)) != self.root:
            raise TrustStoreError(
                "Trust store path cannot contain symlinks",
                TrustStoreReason.UNSAFE_PATH,
            )
        canonical_root = self.root.resolve(strict=False)
        workspace = self.workspace_root
        if (
            canonical_root == workspace
            or canonical_root.is_relative_to(workspace)
            or workspace.is_relative_to(canonical_root)
        ):
            raise TrustStoreError(
                "Trust store must not overlap the Agent workspace",
                TrustStoreReason.WORKSPACE_OVERLAP,
            )

        missing: list[Path] = []
        cursor = self.root
        while not cursor.exists():
            if cursor.parent == cursor:
                raise TrustStoreError(
                    "Trust store has no secure user-owned ancestor",
                    TrustStoreReason.UNSAFE_PATH,
                )
            missing.append(cursor)
            cursor = cursor.parent
        self._validate_existing_directory(cursor, strict=False)
        for directory in reversed(missing):
            try:
                directory.mkdir(mode=TRUST_DIRECTORY_MODE)
            except OSError as exc:
                raise TrustStoreError(
                    "Trust store directory could not be created",
                    TrustStoreReason.IO_FAILURE,
                ) from exc
            self._validate_existing_directory(directory, strict=True)
        self._validate_existing_directory(self.root, strict=True)

    def _validate_existing_directory(self, path: Path, *, strict: bool) -> None:
        try:
            details = path.lstat()
        except OSError as exc:
            raise TrustStoreError(
                "Trust store path could not be inspected",
                TrustStoreReason.IO_FAILURE,
            ) from exc
        if stat.S_ISLNK(details.st_mode) or not stat.S_ISDIR(details.st_mode):
            raise TrustStoreError(
                "Trust store path is not a non-symlink directory",
                TrustStoreReason.UNSAFE_PATH,
            )
        if details.st_uid != os.getuid():
            raise TrustStoreError(
                "Trust store path is not owned by the current user",
                TrustStoreReason.OWNERSHIP,
            )
        forbidden = 0o077 if strict else 0o022
        if stat.S_IMODE(details.st_mode) & forbidden:
            raise TrustStoreError(
                "Trust store path permissions are unsafe",
                TrustStoreReason.PERMISSIONS,
            )

    def _ensure_offline_path(self, path: Path) -> None:
        if os.name != "posix" or not hasattr(os, "getuid"):
            raise TrustStoreError(
                "Trust store ownership checks require POSIX",
                TrustStoreReason.UNSUPPORTED_PLATFORM,
            )
        if Path(os.path.realpath(path)) != path:
            raise TrustStoreError(
                "Offline trust state path cannot contain symlinks",
                TrustStoreReason.UNSAFE_PATH,
            )
        canonical = path.resolve(strict=False)
        workspace = self.workspace_root
        if (
            canonical == workspace
            or canonical.is_relative_to(workspace)
            or workspace.is_relative_to(canonical)
        ):
            raise TrustStoreError(
                "Offline trust state must not overlap the workspace",
                TrustStoreReason.WORKSPACE_OVERLAP,
            )
        self._validate_existing_directory(path.parent, strict=True)

    @staticmethod
    def _validate_fd(
        descriptor: int,
        *,
        directory: bool,
        strict_directory: bool = False,
    ) -> None:
        details = os.fstat(descriptor)
        expected = stat.S_ISDIR if directory else stat.S_ISREG
        if not expected(details.st_mode):
            raise TrustStoreError(
                "Trust store component has an unsafe type",
                TrustStoreReason.UNSAFE_PATH,
            )
        if details.st_uid != os.getuid():
            raise TrustStoreError(
                "Trust store component has an unsafe owner",
                TrustStoreReason.OWNERSHIP,
            )
        forbidden = 0o077 if (strict_directory or not directory) else 0o022
        if stat.S_IMODE(details.st_mode) & forbidden:
            raise TrustStoreError(
                "Trust store component permissions are unsafe",
                TrustStoreReason.PERMISSIONS,
            )

    def _read_locked(self, root_fd: int) -> TrustStoreDocument:
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(TRUST_STATE_FILENAME, flags, dir_fd=root_fd)
        except FileNotFoundError:
            return TrustStoreDocument()
        except OSError as exc:
            raise TrustStoreError(
                "Trust store state could not be opened",
                TrustStoreReason.IO_FAILURE,
            ) from exc
        try:
            self._validate_fd(descriptor, directory=False)
            chunks: list[bytes] = []
            while True:
                chunk = os.read(descriptor, 65536)
                if not chunk:
                    break
                chunks.append(chunk)
        except OSError as exc:
            raise TrustStoreError(
                "Trust store state could not be read",
                TrustStoreReason.IO_FAILURE,
            ) from exc
        finally:
            os.close(descriptor)
        raw = b"".join(chunks)
        try:
            text = raw.decode("utf-8")
            data = json.loads(text)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise TrustStoreError(
                "Trust store is not valid UTF-8 JSON",
                TrustStoreReason.CORRUPT,
            ) from exc
        if not isinstance(data, dict):
            raise TrustStoreError(
                "Trust store document must be a JSON object",
                TrustStoreReason.CORRUPT,
            )
        version = data.get("schema_version")
        if (
            isinstance(version, bool)
            or not isinstance(version, int)
            or version != TRUST_STORE_SCHEMA_VERSION
        ):
            raise TrustStoreError(
                "Trust store schema version is unsupported",
                TrustStoreReason.INVALID_SCHEMA,
            )
        try:
            return TrustStoreDocument.model_validate(data)
        except ValueError as exc:
            raise TrustStoreError(
                "Trust store document failed strict validation",
                TrustStoreReason.CORRUPT,
            ) from exc

    def _write_locked(
        self,
        root_fd: int,
        document: TrustStoreDocument,
    ) -> None:
        encoded = (
            json.dumps(
                document.model_dump(mode="json"),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")
        temporary = f".grants.{secrets.token_hex(16)}.tmp"
        flags = (
            os.O_CREAT
            | os.O_EXCL
            | os.O_WRONLY
            | getattr(os, "O_NOFOLLOW", 0)
        )
        descriptor: int | None = None
        try:
            descriptor = os.open(
                temporary,
                flags,
                TRUST_FILE_MODE,
                dir_fd=root_fd,
            )
            self._validate_fd(descriptor, directory=False)
            offset = 0
            while offset < len(encoded):
                offset += os.write(descriptor, encoded[offset:])
            os.fsync(descriptor)
            os.close(descriptor)
            descriptor = None
            os.replace(
                temporary,
                TRUST_STATE_FILENAME,
                src_dir_fd=root_fd,
                dst_dir_fd=root_fd,
            )
            os.fsync(root_fd)
        except (OSError, TrustStoreError) as exc:
            if isinstance(exc, TrustStoreError):
                raise
            raise TrustStoreError(
                "Trust store atomic replacement failed",
                TrustStoreReason.IO_FAILURE,
            ) from exc
        finally:
            if descriptor is not None:
                os.close(descriptor)
            try:
                os.unlink(temporary, dir_fd=root_fd)
            except FileNotFoundError:
                pass
            except OSError:
                pass

    def _validate_clock(
        self,
        document: TrustStoreDocument,
        now: datetime,
    ) -> None:
        current = _aware_utc(now, "now")
        latest = max(
            (
                timestamp
                for grant in document.grants
                for timestamp in (grant.created_at, grant.revoked_at)
                if timestamp is not None
            ),
            default=None,
        )
        if latest is not None and current < latest:
            raise TrustStoreError(
                "Trust store clock moved before persisted lifecycle state",
                TrustStoreReason.CLOCK_INVALID,
            )

    def _now(self) -> datetime:
        return _aware_utc(self._clock(), "clock result")


def trust_management_binding(
    principal: Principal,
    store_root: Path | str,
    session_id: str,
    operation: TrustOperation,
    arguments: Mapping[str, Any],
) -> AuthenticationBinding:
    """Build the exact one-use authentication binding for one store operation."""

    if not isinstance(principal, Principal):
        raise ValueError("Trust management principal is invalid")
    principal.__post_init__()
    if not isinstance(session_id, str) or not session_id.strip():
        raise ValueError("Trust management session_id must be non-empty")
    if not isinstance(operation, TrustOperation):
        raise ValueError("Trust management operation is invalid")
    try:
        envelope = json.dumps(
            {
                "operation": operation.value,
                "arguments": dict(arguments),
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("Trust management arguments must be canonical JSON") from exc
    canonical_root = str(
        Path(os.path.abspath(os.path.expanduser(str(store_root)))).resolve(strict=False)
    )
    return AuthenticationBinding(
        principal_ref=principal.audit_ref,
        workspace_ref=masked_reference(canonical_root),
        session_id=session_id,
        purpose=TRUST_MANAGEMENT_PURPOSE,
        action_ref=masked_reference(envelope),
    )


class TrustGrantStore:
    """Authenticated user-owned grant administration and exact lookup API."""

    def __init__(
        self,
        workspace_root: Path | str,
        *,
        root: Path | str | None = None,
        clock: Clock = _utc_now,
    ) -> None:
        self._clock = clock
        self._repository = _TrustGrantRepository(
            root or default_trust_store_root(),
            workspace_root,
            clock=clock,
        )

    @property
    def root(self) -> Path:
        return self._repository.root

    @property
    def workspace_root(self) -> Path:
        return self._repository.workspace_root

    @property
    def state_path(self) -> Path:
        return self._repository.state_path

    @property
    def audit_path(self) -> Path:
        return self._repository.audit_path

    def service_authentication(
        self,
        verifier: SecretStr,
        *,
        request_id: str,
        session_id: str,
    ) -> tuple[AuthenticationManager, ServiceStepUpProvider]:
        """Create run-local service authentication audited under the user store."""

        _require_correlation(request_id, session_id)
        logger = self._repository.audit_logger()
        sink = authentication_audit_sink(
            logger,
            request_id=request_id,
            session_id=session_id,
        )
        manager = AuthenticationManager(
            verifier,
            clock=self._clock,
            event_sink=sink,
        )
        return manager, ServiceStepUpProvider(manager, verifier)

    def grant(
        self,
        principal: Principal,
        action: str,
        resource: Mapping[str, Any],
        scopes: Iterable[PrincipalScope | str],
        *,
        session_id: str,
        request_id: str,
        authentication_manager: AuthenticationManager | None,
        step_up_provider: StepUpProvider | None,
        expires_at: datetime | None = None,
    ) -> TrustGrant:
        logger = self._repository.audit_logger()
        _require_correlation(request_id, session_id)
        try:
            grant = build_trust_grant(
                principal,
                action,
                resource,
                scopes,
                created_at=self._now(),
                expires_at=expires_at,
            )
        except (TypeError, ValueError) as exc:
            self._record(
                logger,
                operation=TrustOperation.GRANT,
                success=False,
                reason=TrustStoreReason.INVALID_REQUEST.value,
                principal=principal if isinstance(principal, Principal) else None,
                session_id=session_id,
                request_id=request_id,
                action=action,
                resource=resource if isinstance(resource, Mapping) else None,
            )
            raise TrustStoreError(
                "Trust grant request is invalid",
                TrustStoreReason.INVALID_REQUEST,
            ) from exc
        arguments = {
            "action": grant.action,
            "resource": grant.resource,
            "scopes": [scope.value for scope in grant.scopes],
            "expires_at": (
                None if grant.expires_at is None else grant.expires_at.isoformat()
            ),
        }
        self._authenticate(
            logger,
            principal,
            TrustOperation.GRANT,
            arguments,
            required_scope=PrincipalScope.HIGH_RISK_MANAGE,
            session_id=session_id,
            request_id=request_id,
            authentication_manager=authentication_manager,
            step_up_provider=step_up_provider,
            action=grant.action,
            resource=grant.resource,
            scopes=grant.scopes,
        )
        try:
            self._repository.add(grant)
        except TrustStoreError as exc:
            self._record(
                logger,
                operation=TrustOperation.GRANT,
                success=False,
                reason=exc.reason.value,
                principal=principal,
                session_id=session_id,
                request_id=request_id,
                grant=grant,
            )
            raise
        self._record(
            logger,
            operation=TrustOperation.GRANT,
            success=True,
            reason="trust_grant_created",
            principal=principal,
            session_id=session_id,
            request_id=request_id,
            grant=grant,
        )
        return grant

    def revoke(
        self,
        principal: Principal,
        grant_id: str,
        *,
        session_id: str,
        request_id: str,
        authentication_manager: AuthenticationManager | None,
        step_up_provider: StepUpProvider | None,
    ) -> TrustGrant:
        logger = self._repository.audit_logger()
        _require_correlation(request_id, session_id)
        arguments = {"grant_id": grant_id}
        self._authenticate(
            logger,
            principal,
            TrustOperation.REVOKE,
            arguments,
            required_scope=PrincipalScope.HIGH_RISK_MANAGE,
            session_id=session_id,
            request_id=request_id,
            authentication_manager=authentication_manager,
            step_up_provider=step_up_provider,
            grant_id=grant_id,
        )
        try:
            document = self._repository.read_document()
            grant = next(
                item for item in document.grants if item.grant_id == grant_id
            )
        except StopIteration as exc:
            error = TrustStoreError(
                "Trust grant does not exist",
                TrustStoreReason.GRANT_NOT_FOUND,
            )
            self._record(
                logger,
                operation=TrustOperation.REVOKE,
                success=False,
                reason=error.reason.value,
                principal=principal,
                session_id=session_id,
                request_id=request_id,
                grant_id=grant_id,
            )
            raise error from exc
        except TrustStoreError as exc:
            self._record(
                logger,
                operation=TrustOperation.REVOKE,
                success=False,
                reason=exc.reason.value,
                principal=principal,
                session_id=session_id,
                request_id=request_id,
                grant_id=grant_id,
            )
            raise
        if (
            grant.principal_ref != principal.audit_ref
            or grant.created_by_ref != principal.audit_ref
        ):
            self._record(
                logger,
                operation=TrustOperation.REVOKE,
                success=False,
                reason=TrustStoreReason.PRINCIPAL_MISMATCH.value,
                principal=principal,
                session_id=session_id,
                request_id=request_id,
                grant=grant,
            )
            raise TrustStoreError(
                "Trust grant is bound to another principal",
                TrustStoreReason.PRINCIPAL_MISMATCH,
            )
        try:
            updated = self._repository.revoke(
                grant_id,
                principal.audit_ref,
                revoked_at=self._now(),
            )
            revoked = next(item for item in updated.grants if item.grant_id == grant_id)
        except TrustStoreError as exc:
            self._record(
                logger,
                operation=TrustOperation.REVOKE,
                success=False,
                reason=exc.reason.value,
                principal=principal,
                session_id=session_id,
                request_id=request_id,
                grant=grant,
            )
            raise
        self._record(
            logger,
            operation=TrustOperation.REVOKE,
            success=True,
            reason="trust_grant_revoked",
            principal=principal,
            session_id=session_id,
            request_id=request_id,
            grant=revoked,
        )
        return revoked

    def list(
        self,
        principal: Principal,
        *,
        session_id: str,
        request_id: str,
        authentication_manager: AuthenticationManager | None,
        step_up_provider: StepUpProvider | None,
        include_inactive: bool = False,
    ) -> tuple[TrustGrant, ...]:
        logger = self._repository.audit_logger()
        _require_correlation(request_id, session_id)
        arguments = {"include_inactive": include_inactive}
        self._authenticate(
            logger,
            principal,
            TrustOperation.LIST,
            arguments,
            required_scope=PrincipalScope.READ,
            session_id=session_id,
            request_id=request_id,
            authentication_manager=authentication_manager,
            step_up_provider=step_up_provider,
        )
        try:
            document = self._repository.read_document()
            now = self._now()
            grants = tuple(
                grant
                for grant in document.grants
                if grant.principal_ref == principal.audit_ref
                and (include_inactive or grant.is_active(now))
            )
        except TrustStoreError as exc:
            self._record(
                logger,
                operation=TrustOperation.LIST,
                success=False,
                reason=exc.reason.value,
                principal=principal,
                session_id=session_id,
                request_id=request_id,
            )
            raise
        self._record(
            logger,
            operation=TrustOperation.LIST,
            success=True,
            reason="trust_grants_listed",
            principal=principal,
            session_id=session_id,
            request_id=request_id,
            count=len(grants),
        )
        return grants

    def lookup(
        self,
        principal: Principal,
        action: str,
        resource: Mapping[str, Any],
        required_scopes: Iterable[PrincipalScope | str],
        *,
        session_id: str,
        request_id: str,
    ) -> GrantLookupDecision:
        logger = self._repository.audit_logger()
        _require_correlation(request_id, session_id)
        parsed_scopes = _parse_scope_set(required_scopes)
        try:
            decision = self._repository.lookup(
                principal,
                action,
                resource,
                parsed_scopes,
                now=self._now(),
            )
        except (TrustStoreError, ValueError) as exc:
            reason = (
                exc.reason.value
                if isinstance(exc, TrustStoreError)
                else TrustStoreReason.INVALID_REQUEST.value
            )
            self._record(
                logger,
                operation="lookup",
                success=False,
                reason=reason,
                principal=principal,
                session_id=session_id,
                request_id=request_id,
                action=action,
                resource=resource,
                scopes=parsed_scopes,
            )
            if isinstance(exc, TrustStoreError):
                raise
            raise TrustStoreError(
                "Trust grant lookup request is invalid",
                TrustStoreReason.INVALID_REQUEST,
            ) from exc
        self._record(
            logger,
            operation="lookup",
            success=decision.allowed,
            reason=decision.reason.value,
            principal=principal,
            session_id=session_id,
            request_id=request_id,
            action=action,
            resource=resource,
            scopes=parsed_scopes,
            grant_ref=decision.grant_ref,
        )
        return decision

    def _authenticate(
        self,
        logger: AuditLogger,
        principal: Principal,
        operation: TrustOperation,
        arguments: Mapping[str, Any],
        *,
        required_scope: PrincipalScope,
        session_id: str,
        request_id: str,
        authentication_manager: AuthenticationManager | None,
        step_up_provider: StepUpProvider | None,
        action: str | None = None,
        resource: Mapping[str, Any] | None = None,
        scopes: Iterable[PrincipalScope] = (),
        grant_id: str | None = None,
    ) -> AuthenticationBinding:
        try:
            principal.__post_init__()
        except (AttributeError, ValueError) as exc:
            self._record(
                logger,
                operation=operation,
                success=False,
                reason=TrustStoreReason.INVALID_REQUEST.value,
                principal=None,
                session_id=session_id,
                request_id=request_id,
            )
            raise TrustStoreError(
                "Trust management principal is invalid",
                TrustStoreReason.INVALID_REQUEST,
            ) from exc
        if required_scope not in principal.scopes:
            self._record(
                logger,
                operation=operation,
                success=False,
                reason=TrustStoreReason.SCOPE_INSUFFICIENT.value,
                principal=principal,
                session_id=session_id,
                request_id=request_id,
                action=action,
                resource=resource,
                scopes=scopes,
                grant_id=grant_id,
            )
            raise TrustStoreError(
                "Council principal lacks the required trust management scope",
                TrustStoreReason.SCOPE_INSUFFICIENT,
            )
        binding = trust_management_binding(
            principal,
            self.root,
            session_id,
            operation,
            arguments,
        )
        if authentication_manager is None or step_up_provider is None:
            self._record(
                logger,
                operation=operation,
                success=False,
                reason=TrustStoreReason.AUTHENTICATION_MISSING.value,
                principal=principal,
                session_id=session_id,
                request_id=request_id,
                action=action,
                resource=resource,
                scopes=scopes,
                grant_id=grant_id,
            )
            raise TrustStoreError(
                "Fresh trust management authentication is required",
                TrustStoreReason.AUTHENTICATION_MISSING,
            )
        try:
            token = step_up_provider(binding)
            decision = (
                None
                if token is None
                else authentication_manager.consume_step_up(token, binding)
            )
        except Exception as exc:
            self._record(
                logger,
                operation=operation,
                success=False,
                reason=TrustStoreReason.AUTHENTICATION_DENIED.value,
                principal=principal,
                session_id=session_id,
                request_id=request_id,
                action=action,
                resource=resource,
                scopes=scopes,
                grant_id=grant_id,
            )
            raise TrustStoreError(
                "Trust management authentication failed",
                TrustStoreReason.AUTHENTICATION_DENIED,
            ) from exc
        if (
            decision is None
            or not decision.allowed
            or decision.reason is not AuthenticationReason.STEP_UP_ALLOWED
        ):
            self._record(
                logger,
                operation=operation,
                success=False,
                reason=TrustStoreReason.AUTHENTICATION_DENIED.value,
                principal=principal,
                session_id=session_id,
                request_id=request_id,
                action=action,
                resource=resource,
                scopes=scopes,
                grant_id=grant_id,
                authentication_reason=(
                    AuthenticationReason.MISSING.value
                    if decision is None
                    else decision.reason.value
                ),
            )
            raise TrustStoreError(
                "Trust management authentication was denied",
                TrustStoreReason.AUTHENTICATION_DENIED,
            )
        self._record(
            logger,
            operation=operation,
            success=True,
            reason="trust_authentication_succeeded",
            principal=principal,
            session_id=session_id,
            request_id=request_id,
            action=action,
            resource=resource,
            scopes=scopes,
            grant_id=grant_id,
            authentication_reason=decision.reason.value,
        )
        return binding

    def _record(
        self,
        logger: AuditLogger,
        *,
        operation: TrustOperation | str,
        success: bool,
        reason: str,
        principal: Principal | None,
        session_id: str,
        request_id: str,
        action: str | None = None,
        resource: Mapping[str, Any] | None = None,
        scopes: Iterable[PrincipalScope] = (),
        grant: TrustGrant | None = None,
        grant_id: str | None = None,
        grant_ref: str | None = None,
        count: int | None = None,
        authentication_reason: str | None = None,
    ) -> None:
        operation_value = (
            operation.value if isinstance(operation, TrustOperation) else operation
        )
        target_action = grant.action if grant is not None else action
        target_resource = grant.resource if grant is not None else resource
        target_scopes = grant.scopes if grant is not None else tuple(scopes)
        resolved_grant_ref = (
            grant.grant_ref
            if grant is not None
            else grant_ref
            if grant_ref is not None
            else masked_reference(grant_id)
            if grant_id
            else None
        )
        metadata = {
            "operation": operation_value,
            "reason": reason,
            "store_ref": masked_reference(str(self.root)),
            "principal_ref": None if principal is None else principal.audit_ref,
            "creator_ref": None if grant is None else grant.created_by_ref,
            "grant_ref": resolved_grant_ref,
            "action_ref": (
                None if target_action is None else masked_reference(target_action)
            ),
            "resource_ref": _resource_reference(target_resource),
            "scopes": sorted(
                scope.value for scope in target_scopes if isinstance(scope, PrincipalScope)
            ),
            "count": count,
            "authentication_reason": authentication_reason,
        }
        try:
            logger.record(
                "trust_grant_store",
                {
                    "operation": operation_value,
                    "grant_ref": resolved_grant_ref,
                    "action_ref": metadata["action_ref"],
                    "resource_ref": metadata["resource_ref"],
                },
                success=success,
                error=None if success else reason,
                metadata={"trust_grant": metadata},
                session_id=session_id,
                request_id=request_id,
                decision="allow" if success else "deny",
            )
        except Exception as exc:
            raise TrustStoreError(
                "Trust grant audit evidence could not be persisted",
                TrustStoreReason.AUDIT_FAILURE,
            ) from exc

    def _now(self) -> datetime:
        return _aware_utc(self._clock(), "clock result")


def _require_correlation(request_id: str, session_id: str) -> None:
    if not isinstance(request_id, str) or not request_id.strip():
        raise ValueError("Trust management request_id must be non-empty")
    if not isinstance(session_id, str) or not session_id.strip():
        raise ValueError("Trust management session_id must be non-empty")


def _resource_reference(resource: Mapping[str, Any] | None) -> str | None:
    if resource is None:
        return None
    try:
        canonical = canonical_resource_json(resource)
    except (TypeError, ValueError):
        return masked_reference("invalid-trust-resource")
    return masked_reference(canonical)


def _parse_scope_set(
    scopes: Iterable[PrincipalScope | str],
) -> frozenset[PrincipalScope]:
    parsed: set[PrincipalScope] = set()
    for scope in scopes:
        try:
            parsed.add(scope if isinstance(scope, PrincipalScope) else PrincipalScope(scope))
        except (TypeError, ValueError) as exc:
            raise ValueError("Trust grant contains an unknown scope") from exc
    if not parsed:
        raise ValueError("Trust grant scopes must be non-empty")
    return frozenset(parsed)


def validate_trust_store_file(
    state_path: Path | str,
    workspace_root: Path | str,
) -> TrustStoreDocument:
    """Validate one offline state file without creating, locking, or repairing it."""

    path = Path(os.path.abspath(os.path.expanduser(str(state_path))))
    repository = _TrustGrantRepository(path.parent, workspace_root)
    repository._ensure_offline_path(path)
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise TrustStoreError(
            "Offline trust state could not be opened",
            TrustStoreReason.IO_FAILURE,
        ) from exc
    try:
        repository._validate_fd(descriptor, directory=False)
        raw = b""
        while True:
            chunk = os.read(descriptor, 65536)
            if not chunk:
                break
            raw += chunk
    finally:
        os.close(descriptor)
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TrustStoreError(
            "Offline trust state is not valid UTF-8 JSON",
            TrustStoreReason.CORRUPT,
        ) from exc
    if not isinstance(data, dict):
        raise TrustStoreError(
            "Offline trust state must be a JSON object",
            TrustStoreReason.CORRUPT,
        )
    version = data.get("schema_version")
    if (
        isinstance(version, bool)
        or not isinstance(version, int)
        or version != TRUST_STORE_SCHEMA_VERSION
    ):
        raise TrustStoreError(
            "Offline trust state schema is unsupported",
            TrustStoreReason.INVALID_SCHEMA,
        )
    try:
        return TrustStoreDocument.model_validate(data)
    except ValueError as exc:
        raise TrustStoreError(
            "Offline trust state failed strict validation",
            TrustStoreReason.CORRUPT,
        ) from exc
