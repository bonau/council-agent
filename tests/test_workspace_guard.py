"""Tests for WorkspaceGuard path boundary enforcement."""

from __future__ import annotations

from pathlib import Path

import pytest

from council_agent.sandbox.workspace import WorkspaceGuard, WorkspaceGuardError
from council_agent.security import CouncilPolicy, active_policy


@pytest.fixture
def guard(tmp_path: Path) -> WorkspaceGuard:
    return WorkspaceGuard(tmp_path)


def test_resolve_relative_path_inside_workspace(guard: WorkspaceGuard, tmp_path: Path) -> None:
    target = tmp_path / "file.txt"
    target.write_text("ok", encoding="utf-8")
    resolved = guard.resolve("file.txt")
    assert resolved == target.resolve()


def test_resolve_absolute_path_inside_workspace(guard: WorkspaceGuard, tmp_path: Path) -> None:
    target = tmp_path / "nested" / "file.txt"
    target.parent.mkdir(parents=True)
    target.write_text("ok", encoding="utf-8")
    resolved = guard.resolve(str(target))
    assert resolved == target.resolve()


def test_resolve_workspace_root(guard: WorkspaceGuard, tmp_path: Path) -> None:
    resolved = guard.resolve(".")
    assert resolved == tmp_path.resolve()


def test_resolve_path_traversal_blocked(guard: WorkspaceGuard, tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside_guard_test.txt"
    outside.write_text("secret", encoding="utf-8")
    try:
        with pytest.raises(WorkspaceGuardError, match="outside workspace"):
            guard.resolve(f"../{outside.name}")
    finally:
        outside.unlink(missing_ok=True)


def test_resolve_symlink_escape_blocked(guard: WorkspaceGuard, tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside_symlink_target.txt"
    outside.write_text("secret", encoding="utf-8")
    link = tmp_path / "escape_link"
    link.symlink_to(outside)
    try:
        with pytest.raises(WorkspaceGuardError, match="outside workspace"):
            guard.resolve("escape_link")
    finally:
        link.unlink(missing_ok=True)
        outside.unlink(missing_ok=True)


def test_resolve_symlink_within_workspace_allowed(
    guard: WorkspaceGuard, tmp_path: Path
) -> None:
    target = tmp_path / "real.txt"
    target.write_text("ok", encoding="utf-8")
    link = tmp_path / "link.txt"
    link.symlink_to(target)
    resolved = guard.resolve("link.txt")
    assert resolved == target.resolve()


def test_resolve_denied_env(guard: WorkspaceGuard, tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("SECRET=1", encoding="utf-8")
    with pytest.raises(WorkspaceGuardError, match="denied"):
        guard.resolve(".env")


def test_resolve_denied_git_config(guard: WorkspaceGuard, tmp_path: Path) -> None:
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    (git_dir / "config").write_text("[core]", encoding="utf-8")
    with pytest.raises(WorkspaceGuardError, match="denied"):
        guard.resolve(".git/config")


def test_resolve_denied_council_secrets(guard: WorkspaceGuard, tmp_path: Path) -> None:
    secrets = tmp_path / ".council" / "secrets"
    secrets.mkdir(parents=True)
    key = secrets / "api.key"
    key.write_text("secret", encoding="utf-8")
    with pytest.raises(WorkspaceGuardError, match="denied"):
        guard.resolve(".council/secrets/api.key")


def test_resolve_new_file_in_workspace(guard: WorkspaceGuard) -> None:
    resolved = guard.resolve("new/nested/file.txt")
    assert resolved.name == "file.txt"


def test_resolve_new_denied_file_blocked(guard: WorkspaceGuard) -> None:
    with pytest.raises(WorkspaceGuardError, match="denied"):
        guard.resolve(".env")


def test_list_workspace_root_allowed_with_sensitive_entries(
    guard: WorkspaceGuard, tmp_path: Path
) -> None:
    (tmp_path / ".env").write_text("SECRET=1", encoding="utf-8")
    (tmp_path / "readme.txt").write_text("hi", encoding="utf-8")
    resolved = guard.resolve(".")
    assert resolved == tmp_path.resolve()


def test_resolve_cwd_defaults_to_root(guard: WorkspaceGuard, tmp_path: Path) -> None:
    assert guard.resolve_cwd(None) == tmp_path.resolve()


def test_resolve_cwd_inside_workspace(guard: WorkspaceGuard, tmp_path: Path) -> None:
    sub = tmp_path / "subdir"
    sub.mkdir()
    assert guard.resolve_cwd("subdir") == sub.resolve()


def test_resolve_cwd_outside_workspace_blocked(guard: WorkspaceGuard) -> None:
    with pytest.raises(WorkspaceGuardError, match="outside workspace"):
        guard.resolve_cwd("..")


def test_guard_rejects_nonexistent_root(tmp_path: Path) -> None:
    missing = tmp_path / "missing_root"
    with pytest.raises(WorkspaceGuardError, match="does not exist"):
        WorkspaceGuard(missing)


def test_guard_rejects_file_root(tmp_path: Path) -> None:
    file_root = tmp_path / "not_a_dir.txt"
    file_root.write_text("x", encoding="utf-8")
    with pytest.raises(WorkspaceGuardError, match="not a directory"):
        WorkspaceGuard(file_root)


def test_policy_denied_path_blocked(guard: WorkspaceGuard, tmp_path: Path) -> None:
    secrets = tmp_path / "secrets"
    secrets.mkdir()
    (secrets / "token.txt").write_text("x", encoding="utf-8")
    policy = CouncilPolicy(denied_paths=["secrets/**"])
    with active_policy(policy):
        with pytest.raises(WorkspaceGuardError, match="denied"):
            guard.resolve("secrets/token.txt")


def test_default_denylist_still_applies_with_policy(
    guard: WorkspaceGuard, tmp_path: Path
) -> None:
    (tmp_path / ".env").write_text("SECRET=1", encoding="utf-8")
    policy = CouncilPolicy(denied_paths=["secrets/**"])
    with active_policy(policy):
        with pytest.raises(WorkspaceGuardError, match="denied"):
            guard.resolve(".env")


def test_no_policy_adds_no_extra_path_denials(
    guard: WorkspaceGuard, tmp_path: Path
) -> None:
    secrets = tmp_path / "secrets"
    secrets.mkdir()
    target = secrets / "token.txt"
    target.write_text("x", encoding="utf-8")
    assert guard.resolve("secrets/token.txt") == target.resolve()
