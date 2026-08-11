"""Sandbox utilities for workspace boundary enforcement and sessions."""

from council_agent.sandbox.config import (
    CouncilConfig,
    apply_workspace_root,
    audit_dir,
    clear_workspace_caches,
    init_sandbox,
    is_sandbox_initialized,
    load_council_config,
    resolve_workspace_root,
)
from council_agent.sandbox.session import SessionManager, SessionMeta
from council_agent.sandbox.workspace import (
    DEFAULT_DENIED_PATTERNS,
    DeniedPathError,
    WorkspaceBoundaryError,
    WorkspaceGuard,
    WorkspaceGuardError,
    get_workspace_guard,
)

__all__ = [
    "CouncilConfig",
    "DEFAULT_DENIED_PATTERNS",
    "DeniedPathError",
    "SessionManager",
    "SessionMeta",
    "WorkspaceGuard",
    "WorkspaceBoundaryError",
    "WorkspaceGuardError",
    "apply_workspace_root",
    "audit_dir",
    "clear_workspace_caches",
    "get_workspace_guard",
    "init_sandbox",
    "is_sandbox_initialized",
    "load_council_config",
    "resolve_workspace_root",
]
