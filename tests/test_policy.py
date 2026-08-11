"""Unit tests for council.policy.yaml loading and evaluation."""

from __future__ import annotations

from pathlib import Path

import pytest

from council_agent.sandbox.workspace import DEFAULT_DENIED_PATTERNS
from council_agent.security import (
    CouncilPolicy,
    PolicyCommandReason,
    PolicyValidationError,
    active_policy,
    effective_denied_paths,
    evaluate_command,
    get_active_policy,
    load_policy_file,
    policy_path,
)


def test_missing_policy_file_returns_none(tmp_path: Path) -> None:
    assert load_policy_file(tmp_path) is None


def test_policy_path_is_project_root_file(tmp_path: Path) -> None:
    assert policy_path(tmp_path) == tmp_path / "council.policy.yaml"


def test_valid_policy_loads(tmp_path: Path) -> None:
    (tmp_path / "council.policy.yaml").write_text(
        "\n".join(
            [
                "allowed_commands:",
                '  - "pytest *"',
                "denied_commands:",
                '  - "curl *"',
                "denied_paths:",
                '  - "secrets/**"',
                "trust_tier: 1",
                "",
            ]
        ),
        encoding="utf-8",
    )
    policy = load_policy_file(tmp_path)
    assert policy is not None
    assert policy.allowed_commands == ["pytest *"]
    assert policy.denied_commands == ["curl *"]
    assert policy.denied_paths == ["secrets/**"]
    assert not hasattr(policy, "trust_tier")


def test_invalid_policy_type_raises(tmp_path: Path) -> None:
    (tmp_path / "council.policy.yaml").write_text(
        "denied_commands: not-a-list\n",
        encoding="utf-8",
    )
    with pytest.raises(PolicyValidationError, match="Invalid policy"):
        load_policy_file(tmp_path)


def test_invalid_yaml_raises(tmp_path: Path) -> None:
    (tmp_path / "council.policy.yaml").write_text(
        "denied_commands: [\n",
        encoding="utf-8",
    )
    with pytest.raises(PolicyValidationError, match="Invalid YAML"):
        load_policy_file(tmp_path)


def test_top_level_non_mapping_raises(tmp_path: Path) -> None:
    (tmp_path / "council.policy.yaml").write_text(
        "- just a list\n",
        encoding="utf-8",
    )
    with pytest.raises(PolicyValidationError, match="mapping"):
        load_policy_file(tmp_path)


def test_empty_file_loads_as_empty_policy(tmp_path: Path) -> None:
    (tmp_path / "council.policy.yaml").write_text("", encoding="utf-8")
    policy = load_policy_file(tmp_path)
    assert policy == CouncilPolicy()


def test_deny_over_allow() -> None:
    policy = CouncilPolicy(
        allowed_commands=["curl *"],
        denied_commands=["curl *"],
    )
    decision = evaluate_command("curl https://example.com", policy)
    assert decision.allowed is False
    assert decision.reason is PolicyCommandReason.DENIED
    assert decision.matched_pattern == "curl *"


def test_allowlist_refuses_non_matching() -> None:
    policy = CouncilPolicy(allowed_commands=["pytest *"])
    decision = evaluate_command("echo hello", policy)
    assert decision.allowed is False
    assert decision.reason is PolicyCommandReason.NOT_ALLOWED


def test_allowlist_permits_matching() -> None:
    policy = CouncilPolicy(allowed_commands=["pytest *"])
    decision = evaluate_command("pytest -q", policy)
    assert decision.allowed is True
    assert decision.reason is None


def test_empty_allowlist_no_restriction() -> None:
    policy = CouncilPolicy(allowed_commands=[], denied_commands=[])
    decision = evaluate_command("echo hello", policy)
    assert decision.allowed is True


def test_no_policy_allows_all() -> None:
    decision = evaluate_command("curl https://example.com", None)
    assert decision.allowed is True


def test_effective_denied_paths_union() -> None:
    policy = CouncilPolicy(denied_paths=["secrets/**", ".env"])
    paths = effective_denied_paths(policy)
    assert paths[0 : len(DEFAULT_DENIED_PATTERNS)] == DEFAULT_DENIED_PATTERNS
    assert "secrets/**" in paths
    assert paths.count(".env") == 1


def test_effective_denied_paths_without_policy() -> None:
    assert effective_denied_paths(None) == DEFAULT_DENIED_PATTERNS


def test_active_policy_context() -> None:
    policy = CouncilPolicy(denied_commands=["sudo *"])
    assert get_active_policy() is None
    with active_policy(policy):
        assert get_active_policy() is policy
        decision = evaluate_command("sudo true")
        assert decision.allowed is False
    assert get_active_policy() is None
