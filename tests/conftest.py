"""Shared pytest fixtures."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from council_agent.config.settings import get_settings
from council_agent.sandbox.workspace import get_workspace_guard
from council_agent.security.middleware import SecurityContext, security_context
from council_agent.security.principal import full_scope_principal
from council_agent.security.trust import TrustTier
from council_agent.tools.tracker import ToolCallTracker

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def visible_cli_text(text: str) -> str:
    """Strip ANSI SGR sequences so flag names stay contiguous.

    Rich help with colour enabled renders ``--yes`` as ``-`` + reset + ``-yes``,
    so substring checks on the raw buffer fail on GitHub Actions while passing
    locally under ``NO_COLOR=1``.
    """
    return _ANSI_RE.sub("", text)


@pytest.fixture(autouse=True)
def workspace_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point tool workspace guard at the per-test temp directory."""
    monkeypatch.setenv("COUNCIL_WORKSPACE_ROOT", str(tmp_path))
    # Settings requires OPENROUTER_API_KEY; provide a dummy so CI/local
    # runs without a real .env still construct Settings for WorkspaceGuard.
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    get_settings.cache_clear()
    get_workspace_guard.cache_clear()
    context = SecurityContext.create(
        tmp_path,
        request_id=f"pytest-{tmp_path.name}",
        tracker=ToolCallTracker(max_tool_calls=1000),
        principal=full_scope_principal("pytest-suite", issuer="pytest"),
        # Suite default Tier 1 preserves prior read behavior; product CLI
        # still defaults to Tier 0.
        trust_tier=TrustTier.TIER_1,
    )
    with security_context(context):
        yield tmp_path
    get_settings.cache_clear()
    get_workspace_guard.cache_clear()
