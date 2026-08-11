"""Trust Tier translator and runtime consumption tests."""

from __future__ import annotations

from pathlib import Path
from unittest import mock

from council_agent.security import (
    ConfirmMode,
    ConfirmationPolicy,
    GrantLookupDecision,
    GrantLookupReason,
    Principal,
    PrincipalKind,
    PrincipalScope,
    SecurityContext,
    TrustTier,
    full_scope_principal,
    security_context,
    translate_tier,
    without_security_context,
)
from council_agent.security.decision import ActionRisk, GrantState
from council_agent.tools import read_file, write_file


def _principal(*scopes: PrincipalScope) -> Principal:
    return Principal(
        principal_id="tier-user",
        kind=PrincipalKind.LOCAL_USER,
        issuer="pytest",
        scopes=frozenset(scopes),
    )


def test_translate_tier0_requires_confirmation_for_read() -> None:
    result = translate_tier(TrustTier.TIER_0, ActionRisk.READ, None)
    assert result.require_confirmation is True
    assert result.grant_state is GrantState.NOT_REQUIRED


def test_translate_tier1_mutate_grant_allows_auto() -> None:
    lookup = GrantLookupDecision(
        allowed=True,
        reason=GrantLookupReason.ALLOWED,
        principal_ref="sha256:abc",
        required_scopes=frozenset({PrincipalScope.FILESYSTEM_MUTATE}),
        granted_scopes=frozenset({PrincipalScope.FILESYSTEM_MUTATE}),
        grant_ref="sha256:grant",
    )
    result = translate_tier(TrustTier.TIER_1, ActionRisk.MUTATE, lookup)
    assert result.grant_state is GrantState.VALID
    assert result.auto_approve_interaction is True


def test_translate_tier1_mutate_revoked_denies() -> None:
    lookup = GrantLookupDecision(
        allowed=False,
        reason=GrantLookupReason.REVOKED,
        principal_ref="sha256:abc",
        required_scopes=frozenset({PrincipalScope.FILESYSTEM_MUTATE}),
        granted_scopes=frozenset(),
    )
    result = translate_tier(TrustTier.TIER_1, ActionRisk.MUTATE, lookup)
    assert result.grant_state is GrantState.REVOKED
    assert result.auto_approve_interaction is False


def test_tier0_read_refused_without_auto(tmp_path: Path) -> None:
    (tmp_path / "item.txt").write_text("content", encoding="utf-8")
    context = SecurityContext.create(
        tmp_path,
        principal=_principal(PrincipalScope.READ),
        trust_tier=TrustTier.TIER_0,
        confirmation=ConfirmationPolicy(mode=ConfirmMode.REFUSE),
    )
    with without_security_context(), security_context(context):
        result = read_file("item.txt")
    assert result.success is False
    assert result.metadata["rejection_reason"] == "confirmation_refused"
    assert result.metadata["trust_tier"] == 0


def test_tier0_read_auto_allows(tmp_path: Path) -> None:
    (tmp_path / "item.txt").write_text("content", encoding="utf-8")
    context = SecurityContext.create(
        tmp_path,
        principal=_principal(PrincipalScope.READ),
        trust_tier=TrustTier.TIER_0,
        confirmation=ConfirmationPolicy(mode=ConfirmMode.AUTO),
    )
    with without_security_context(), security_context(context):
        result = read_file("item.txt")
    assert result.success is True
    assert result.metadata["trust_decision"]["vector"]["interaction"] == "auto"


def test_tier1_mutate_without_grant_uses_confirm_mode(tmp_path: Path) -> None:
    context = SecurityContext.create(
        tmp_path,
        principal=full_scope_principal("tier1", issuer="pytest"),
        trust_tier=TrustTier.TIER_1,
        confirmation=ConfirmationPolicy(mode=ConfirmMode.REFUSE),
    )
    with without_security_context(), security_context(context):
        result = write_file("blocked.txt", "x")
    assert result.success is False
    assert not (tmp_path / "blocked.txt").exists()
    assert result.metadata["rejection_reason"] == "confirmation_refused"


def test_tier1_mutate_compat_without_grant_allows(tmp_path: Path) -> None:
    context = SecurityContext.create(
        tmp_path,
        principal=full_scope_principal("tier1", issuer="pytest"),
        trust_tier=TrustTier.TIER_1,
        confirmation=ConfirmationPolicy(mode=ConfirmMode.COMPAT),
    )
    with without_security_context(), security_context(context):
        result = write_file("compat.txt", "ok")
    assert result.success is True
    assert (tmp_path / "compat.txt").read_text(encoding="utf-8") == "ok"


def test_tier1_mutate_with_grant_skips_confirmation(tmp_path: Path) -> None:
    context = SecurityContext.create(
        tmp_path,
        principal=full_scope_principal("tier1", issuer="pytest"),
        trust_tier=TrustTier.TIER_1,
        confirmation=ConfirmationPolicy(mode=ConfirmMode.REFUSE),
    )
    allowed = GrantLookupDecision(
        allowed=True,
        reason=GrantLookupReason.ALLOWED,
        principal_ref=context.principal.audit_ref if context.principal else "x",
        required_scopes=frozenset({PrincipalScope.FILESYSTEM_MUTATE}),
        granted_scopes=frozenset({PrincipalScope.FILESYSTEM_MUTATE}),
        grant_ref="sha256:g",
    )
    with (
        without_security_context(),
        security_context(context),
        mock.patch(
            "council_agent.security.middleware._lookup_grant_for_action",
            return_value=allowed,
        ),
    ):
        result = write_file("granted.txt", "ok")
    assert result.success is True
    assert (tmp_path / "granted.txt").read_text(encoding="utf-8") == "ok"
    assert result.metadata["trust_decision"]["vector"]["grant"] == "trust_grant_allowed"


def test_yes_does_not_override_scope_under_tier2(tmp_path: Path) -> None:
    context = SecurityContext.create(
        tmp_path,
        principal=_principal(PrincipalScope.READ),
        trust_tier=TrustTier.TIER_2,
        confirmation=ConfirmationPolicy(mode=ConfirmMode.AUTO),
    )
    with without_security_context(), security_context(context):
        result = write_file("nope.txt", "x")
    assert result.success is False
    assert result.metadata["rejection_reason"] == "scope_insufficient"
    assert not (tmp_path / "nope.txt").exists()
