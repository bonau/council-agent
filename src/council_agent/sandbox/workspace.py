"""Workspace boundary enforcement for tool operations."""

from __future__ import annotations

import fnmatch
from functools import lru_cache
from pathlib import Path

from council_agent.config.settings import get_settings

DEFAULT_DENIED_PATTERNS: tuple[str, ...] = (
    ".env",
    ".git",
    ".git/**",
    ".council/secrets",
    ".council/secrets/**",
    "council.policy.yaml",
    "**/council.policy.yaml",
)


class WorkspaceGuardError(Exception):
    """Raised when a path violates workspace boundary or denylist rules."""


class WorkspaceBoundaryError(WorkspaceGuardError):
    """Raised when a path resolves outside the workspace root."""


class DeniedPathError(WorkspaceGuardError):
    """Raised when a path matches a built-in or active-policy deny pattern."""


class WorkspaceGuard:
    """Validates paths and working directories against a workspace root."""

    def __init__(
        self,
        root: Path,
        denied_patterns: tuple[str, ...] = DEFAULT_DENIED_PATTERNS,
    ) -> None:
        resolved_root = root.resolve()
        if not resolved_root.exists():
            raise WorkspaceGuardError(f"Workspace root does not exist: {root}")
        if not resolved_root.is_dir():
            raise WorkspaceGuardError(f"Workspace root is not a directory: {root}")
        self.root = resolved_root
        self.denied_patterns = denied_patterns

    def resolve(self, path: str) -> Path:
        """Resolve and validate a path within the workspace."""
        return self.resolve_from(self.root, path)

    def resolve_from(self, cwd: Path, path: str) -> Path:
        """Resolve an operand relative to an already validated execution cwd."""

        resolved_cwd = cwd.resolve(strict=False)
        self._ensure_within_root(resolved_cwd)
        self._ensure_not_denied(resolved_cwd)

        candidate = Path(path)
        resolved = (
            candidate.resolve(strict=False)
            if candidate.is_absolute()
            else (resolved_cwd / candidate).resolve(strict=False)
        )
        self._ensure_within_root(resolved)
        self._ensure_not_denied(resolved)
        return resolved

    def resolve_cwd(self, cwd: str | None) -> Path:
        """Resolve and validate a working directory; default to workspace root."""
        if cwd is None:
            return self.root
        return self.resolve(cwd)

    def _ensure_within_root(self, resolved: Path) -> None:
        if resolved == self.root or resolved.is_relative_to(self.root):
            return
        raise WorkspaceBoundaryError(
            f"Path is outside workspace root ({self.root}): {resolved}"
        )

    def _effective_denied_patterns(self) -> tuple[str, ...]:
        """Union of constructed denylist and active policy ``denied_paths``."""
        # Lazy import avoids circular import with security.policy.
        from council_agent.security.policy import get_active_policy

        patterns = list(self.denied_patterns)
        policy = get_active_policy()
        if policy is not None:
            for pattern in policy.denied_paths:
                if pattern not in patterns:
                    patterns.append(pattern)
        return tuple(patterns)

    def _ensure_not_denied(self, resolved: Path) -> None:
        try:
            relative = resolved.relative_to(self.root)
        except ValueError:
            return

        posix = relative.as_posix()
        if posix == ".":
            posix = ""

        for pattern in self._effective_denied_patterns():
            if self._matches_pattern(posix, pattern):
                display = posix or "."
                raise DeniedPathError(f"Access denied for sensitive path: {display}")

    @staticmethod
    def _matches_pattern(posix_path: str, pattern: str) -> bool:
        if pattern.endswith("/**"):
            prefix = pattern[:-3]
            return posix_path == prefix or posix_path.startswith(f"{prefix}/")
        if fnmatch.fnmatch(posix_path, pattern):
            return True
        if "/" not in pattern:
            first = posix_path.split("/", 1)[0] if posix_path else ""
            return fnmatch.fnmatch(first, pattern)
        return False


@lru_cache
def get_workspace_guard() -> WorkspaceGuard:
    settings = get_settings()
    return WorkspaceGuard(settings.council_workspace_root)
