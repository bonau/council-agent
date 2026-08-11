"""Shared pytest fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

from council_agent.config.settings import get_settings
from council_agent.sandbox.workspace import get_workspace_guard
from council_agent.security.middleware import SecurityContext, security_context
from council_agent.tools.tracker import ToolCallTracker


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
    )
    with security_context(context):
        yield tmp_path
    get_settings.cache_clear()
    get_workspace_guard.cache_clear()
