"""Council authorization principals and fail-closed action scopes."""

from __future__ import annotations

import hashlib
import getpass
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Any, TypeAlias

from council_agent.security.classifier import (
    ClassificationResult,
    CommandCategory,
    classify_command,
)


class PrincipalKind(str, Enum):
    """Recognized sources of Council authorization identities."""

    LOCAL_USER = "local-user"
    SERVICE = "service"


class PrincipalScope(str, Enum):
    """Closed set of independently granted product-tool authorities."""

    READ = "read"
    FILESYSTEM_MUTATE = "filesystem:mutate"
    TEST = "test"
    SHELL = "shell"
    HIGH_RISK_MANAGE = "high-risk:manage"


ALL_PRINCIPAL_SCOPES = frozenset(PrincipalScope)


def parse_principal_scopes(value: str | Iterable[str]) -> frozenset[PrincipalScope]:
    """Parse a strict comma-delimited or iterable scope declaration."""

    raw_values = value.split(",") if isinstance(value, str) else list(value)
    scopes: set[PrincipalScope] = set()
    for raw in raw_values:
        if not isinstance(raw, str):
            raise ValueError("Principal scopes must be strings")
        name = raw.strip()
        if not name:
            continue
        try:
            scopes.add(PrincipalScope(name))
        except ValueError as exc:
            raise ValueError("Unknown Council principal scope") from exc
    return frozenset(scopes)


@dataclass(frozen=True)
class Principal:
    """One immutable Council authorization identity and current scope set."""

    principal_id: str
    kind: PrincipalKind
    issuer: str
    scopes: frozenset[PrincipalScope]

    def __post_init__(self) -> None:
        if not isinstance(self.principal_id, str) or not self.principal_id.strip():
            raise ValueError("Principal principal_id must be a non-empty string")
        if not isinstance(self.kind, PrincipalKind):
            raise ValueError("Principal kind is not recognized")
        if not isinstance(self.issuer, str) or not self.issuer.strip():
            raise ValueError("Principal issuer must be a non-empty string")
        if not isinstance(self.scopes, frozenset):
            raise ValueError("Principal scopes must be a frozenset")
        if any(not isinstance(scope, PrincipalScope) for scope in self.scopes):
            raise ValueError("Principal contains an unrecognized scope")

    @property
    def identity(self) -> tuple[str, PrincipalKind, str]:
        """Return the stable identity tuple, excluding mutable authority."""

        return (self.issuer, self.kind, self.principal_id)

    @property
    def audit_ref(self) -> str:
        """Return a stable non-reversible reference safe for evidence."""

        canonical = "\0".join(
            (self.issuer, self.kind.value, self.principal_id)
        ).encode("utf-8")
        digest = hashlib.sha256(canonical).hexdigest()
        return f"sha256:{digest[:32]}"


PrincipalResolver: TypeAlias = Callable[[], Principal | None]


class AuthorizationReason(str, Enum):
    """Stable result reasons for principal/scope authorization."""

    ALLOWED = "scope_allowed"
    PRINCIPAL_MISSING = "principal_missing"
    PRINCIPAL_REVOKED = "principal_revoked"
    PRINCIPAL_INVALID = "principal_invalid"
    PRINCIPAL_MISMATCH = "principal_mismatch"
    SCOPE_INSUFFICIENT = "scope_insufficient"


@dataclass(frozen=True)
class ScopeDecision:
    """One normalized principal/scope decision for a product action."""

    allowed: bool
    reason: AuthorizationReason
    required_scopes: frozenset[PrincipalScope]
    granted_scopes: frozenset[PrincipalScope]
    missing_scopes: frozenset[PrincipalScope]
    principal_ref: str | None = None
    principal_kind: PrincipalKind | None = None

    def to_metadata(self) -> dict[str, Any]:
        """Return a JSON-safe evidence view containing no raw identity."""

        return {
            "principal_ref": self.principal_ref,
            "principal_kind": (
                None if self.principal_kind is None else self.principal_kind.value
            ),
            "required_scopes": _scope_values(self.required_scopes),
            "granted_scopes": _scope_values(self.granted_scopes),
            "missing_scopes": _scope_values(self.missing_scopes),
            "scope_decision": "allow" if self.allowed else "deny",
            "reason": self.reason.value,
        }


_STATIC_TOOL_SCOPES: dict[str, frozenset[PrincipalScope]] = {
    "read_file": frozenset({PrincipalScope.READ}),
    "list_dir": frozenset({PrincipalScope.READ}),
    "write_file": frozenset({PrincipalScope.FILESYSTEM_MUTATE}),
    "delete_file": frozenset({PrincipalScope.FILESYSTEM_MUTATE}),
    "run_tests": frozenset(
        {
            PrincipalScope.TEST,
            PrincipalScope.FILESYSTEM_MUTATE,
        }
    ),
}


def required_scopes_for_action(
    tool_name: str,
    tool_args: Mapping[str, Any],
) -> frozenset[PrincipalScope]:
    """Return cumulative scopes for one canonical top-level tool action."""

    static = _STATIC_TOOL_SCOPES.get(tool_name)
    if static is not None:
        return static
    if tool_name != "run_command":
        raise ValueError(f"Unknown product tool: {tool_name}")

    required = {PrincipalScope.SHELL}
    command = tool_args.get("command")
    if not isinstance(command, str):
        return frozenset(required)
    analysis = classify_command(command)
    if not isinstance(analysis, ClassificationResult):
        return frozenset(required)
    if analysis.category is CommandCategory.READ:
        required.add(PrincipalScope.READ)
    elif analysis.category is CommandCategory.WRITE:
        required.add(PrincipalScope.FILESYSTEM_MUTATE)
    elif analysis.category is CommandCategory.DANGEROUS:
        required.update(
            {
                PrincipalScope.FILESYSTEM_MUTATE,
                PrincipalScope.HIGH_RISK_MANAGE,
            }
        )
    return frozenset(required)


def evaluate_principal_scopes(
    expected: Principal | None,
    current: object,
    required_scopes: frozenset[PrincipalScope],
) -> ScopeDecision:
    """Evaluate current authority against a context-bound identity."""

    if expected is None:
        return _denied(
            AuthorizationReason.PRINCIPAL_MISSING,
            required_scopes,
        )
    if current is None:
        return _denied(
            AuthorizationReason.PRINCIPAL_REVOKED,
            required_scopes,
            principal=expected,
        )
    if not isinstance(current, Principal):
        return _denied(
            AuthorizationReason.PRINCIPAL_INVALID,
            required_scopes,
            principal=expected,
        )
    try:
        current.__post_init__()
    except ValueError:
        return _denied(
            AuthorizationReason.PRINCIPAL_INVALID,
            required_scopes,
            principal=expected,
        )
    if current.identity != expected.identity:
        return _denied(
            AuthorizationReason.PRINCIPAL_MISMATCH,
            required_scopes,
            principal=current,
        )

    missing = required_scopes - current.scopes
    if missing:
        return ScopeDecision(
            allowed=False,
            reason=AuthorizationReason.SCOPE_INSUFFICIENT,
            required_scopes=required_scopes,
            granted_scopes=current.scopes,
            missing_scopes=frozenset(missing),
            principal_ref=current.audit_ref,
            principal_kind=current.kind,
        )
    return ScopeDecision(
        allowed=True,
        reason=AuthorizationReason.ALLOWED,
        required_scopes=required_scopes,
        granted_scopes=current.scopes,
        missing_scopes=frozenset(),
        principal_ref=current.audit_ref,
        principal_kind=current.kind,
    )


def full_scope_principal(
    principal_id: str,
    *,
    kind: PrincipalKind = PrincipalKind.LOCAL_USER,
    issuer: str = "council.local",
) -> Principal:
    """Construct an explicit all-scope principal for trusted local callers."""

    return Principal(
        principal_id=principal_id,
        kind=kind,
        issuer=issuer,
        scopes=ALL_PRINCIPAL_SCOPES,
    )


def local_cli_principal(
    principal_id: str | None = None,
    scopes: str | Iterable[str] = tuple(
        scope.value for scope in PrincipalScope
    ),
) -> Principal:
    """Resolve the CLI's stable local declaration independently of provider keys."""

    resolved_id = (
        f"local-user:{getpass.getuser()}"
        if principal_id is None
        else principal_id
    )
    return Principal(
        principal_id=resolved_id,
        kind=PrincipalKind.LOCAL_USER,
        issuer="council.cli.local",
        scopes=parse_principal_scopes(scopes),
    )


def _scope_values(scopes: frozenset[PrincipalScope]) -> list[str]:
    return sorted(scope.value for scope in scopes)


def _denied(
    reason: AuthorizationReason,
    required_scopes: frozenset[PrincipalScope],
    *,
    principal: Principal | None = None,
) -> ScopeDecision:
    granted = frozenset() if principal is None else principal.scopes
    return ScopeDecision(
        allowed=False,
        reason=reason,
        required_scopes=required_scopes,
        granted_scopes=granted,
        missing_scopes=frozenset(required_scopes - granted),
        principal_ref=None if principal is None else principal.audit_ref,
        principal_kind=None if principal is None else principal.kind,
    )
