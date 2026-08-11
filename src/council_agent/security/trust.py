"""Trust Tier selection and matrix-v1 translator (v1.0-alpha)."""

from __future__ import annotations

from contextvars import ContextVar, Token
from dataclasses import dataclass
from enum import IntEnum
from typing import Any, Mapping

from council_agent.security.decision import ActionRisk, GrantState
from council_agent.security.principal import PrincipalScope
from council_agent.security.trust_grants import GrantLookupDecision, GrantLookupReason


class TrustTier(IntEnum):
    """Product Trust Tier selection."""

    TIER_0 = 0
    TIER_1 = 1
    TIER_2 = 2


@dataclass(frozen=True)
class TierTranslation:
    """Closed grant disposition plus interaction intent for one action."""

    grant_state: GrantState
    auto_approve_interaction: bool
    require_confirmation: bool
    lookup_performed: bool
    lookup_metadata: dict[str, Any] | None = None


_ACTIVE_TRANSLATION: ContextVar[TierTranslation | None] = ContextVar(
    "council_tier_translation",
    default=None,
)


def parse_trust_tier(value: int | str | TrustTier) -> TrustTier:
    """Parse a CLI or library tier value; reject unknowns."""

    if isinstance(value, TrustTier):
        return value
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Trust tier must be 0, 1, or 2") from exc
    try:
        return TrustTier(number)
    except ValueError as exc:
        raise ValueError("Trust tier must be 0, 1, or 2") from exc


def tier_selection_requires_step_up(tier: TrustTier) -> bool:
    """Tier 2 selection is a high-risk management act."""

    return tier is TrustTier.TIER_2


def principal_may_select_tier2(scopes: frozenset[PrincipalScope]) -> bool:
    return PrincipalScope.HIGH_RISK_MANAGE in scopes


def grant_state_from_lookup(decision: GrantLookupDecision) -> GrantState:
    """Map an exact lookup decision onto matrix grant states."""

    if decision.allowed:
        return GrantState.VALID
    mapping = {
        GrantLookupReason.NOT_FOUND: GrantState.MISSING,
        GrantLookupReason.REVOKED: GrantState.REVOKED,
        GrantLookupReason.EXPIRED: GrantState.EXPIRED,
        GrantLookupReason.PRINCIPAL_SCOPE_INSUFFICIENT: (
            GrantState.PRINCIPAL_SCOPE_INSUFFICIENT
        ),
        GrantLookupReason.GRANT_SCOPE_INSUFFICIENT: (
            GrantState.GRANT_SCOPE_INSUFFICIENT
        ),
    }
    return mapping.get(decision.reason, GrantState.INVALID)


def should_lookup_grant(tier: TrustTier, risk: ActionRisk) -> bool:
    """Whether the dispatcher should open the grant store for this action."""

    if risk is ActionRisk.UNRECOGNIZED:
        return False
    if tier is TrustTier.TIER_1 and risk is ActionRisk.MUTATE:
        return True
    if tier is TrustTier.TIER_2:
        return True
    return False


def translate_tier(
    tier: TrustTier,
    risk: ActionRisk,
    lookup: GrantLookupDecision | None,
) -> TierTranslation:
    """Pure tier → grant/interaction translator (no I/O)."""

    meta = None if lookup is None else lookup.to_metadata()

    if risk is ActionRisk.UNRECOGNIZED:
        return TierTranslation(
            grant_state=GrantState.NOT_REQUIRED,
            auto_approve_interaction=False,
            require_confirmation=False,
            lookup_performed=lookup is not None,
            lookup_metadata=meta,
        )

    if tier is TrustTier.TIER_0:
        return TierTranslation(
            grant_state=GrantState.NOT_REQUIRED,
            auto_approve_interaction=False,
            require_confirmation=True,
            lookup_performed=False,
            lookup_metadata=None,
        )

    if tier is TrustTier.TIER_1:
        if risk is ActionRisk.READ:
            return TierTranslation(
                grant_state=GrantState.NOT_REQUIRED,
                # Leave interaction not-required; reads need no prompt at Tier 1.
                auto_approve_interaction=False,
                require_confirmation=False,
                lookup_performed=False,
                lookup_metadata=None,
            )
        if risk is ActionRisk.HIGH_RISK:
            return TierTranslation(
                grant_state=GrantState.NOT_REQUIRED,
                auto_approve_interaction=False,
                require_confirmation=True,
                lookup_performed=False,
                lookup_metadata=None,
            )
        # mutate: matching grant auto-approves; otherwise ConfirmMode applies.
        if lookup is None:
            return TierTranslation(
                grant_state=GrantState.NOT_REQUIRED,
                auto_approve_interaction=False,
                require_confirmation=False,
                lookup_performed=False,
                lookup_metadata=None,
            )
        if lookup.allowed:
            return TierTranslation(
                grant_state=GrantState.VALID,
                auto_approve_interaction=True,
                require_confirmation=False,
                lookup_performed=True,
                lookup_metadata=meta,
            )
        if lookup.reason is GrantLookupReason.NOT_FOUND:
            return TierTranslation(
                grant_state=GrantState.NOT_REQUIRED,
                auto_approve_interaction=False,
                require_confirmation=False,
                lookup_performed=True,
                lookup_metadata=meta,
            )
        return TierTranslation(
            grant_state=grant_state_from_lookup(lookup),
            auto_approve_interaction=False,
            require_confirmation=False,
            lookup_performed=True,
            lookup_metadata=meta,
        )

    # Tier 2
    if lookup is not None and lookup.allowed:
        grant_state = GrantState.VALID
    else:
        grant_state = GrantState.NOT_REQUIRED
    return TierTranslation(
        grant_state=grant_state,
        auto_approve_interaction=True,
        require_confirmation=False,
        lookup_performed=lookup is not None,
        lookup_metadata=meta,
    )


def resource_for_tool(tool_name: str, tool_args: Mapping[str, Any]) -> dict[str, Any]:
    """Build the exact grant resource object for a product tool call."""

    if tool_name in {"read_file", "write_file", "list_dir", "delete_file"}:
        return {"path": str(tool_args.get("path", ""))}
    if tool_name == "run_command":
        return {"command": str(tool_args.get("command", ""))}
    if tool_name == "run_tests":
        resource: dict[str, Any] = {"path": str(tool_args.get("path", "."))}
        args = tool_args.get("args", "")
        if args:
            resource["args"] = str(args)
        return resource
    return dict(tool_args)


def set_active_tier_translation(
    translation: TierTranslation | None,
) -> Token[TierTranslation | None]:
    return _ACTIVE_TRANSLATION.set(translation)


def reset_active_tier_translation(token: Token[TierTranslation | None]) -> None:
    _ACTIVE_TRANSLATION.reset(token)


def get_active_tier_translation() -> TierTranslation | None:
    return _ACTIVE_TRANSLATION.get()
