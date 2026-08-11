"""Unit tests for council.policy.yaml loading and evaluation."""

from __future__ import annotations

from pathlib import Path

import pytest

from council_agent.sandbox.workspace import DEFAULT_DENIED_PATTERNS
from council_agent.security import (
    CURRENT_POLICY_SCHEMA_VERSION,
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
                "schema_version: 1",
                "allowed_commands:",
                '  - "pytest *"',
                "denied_commands:",
                '  - "curl *"',
                "denied_paths:",
                '  - "secrets/**"',
                "",
            ]
        ),
        encoding="utf-8",
    )
    policy = load_policy_file(tmp_path)
    assert policy is not None
    assert policy.schema_version == CURRENT_POLICY_SCHEMA_VERSION
    assert policy.allowed_commands == ["pytest *"]
    assert policy.denied_commands == ["curl *"]
    assert policy.denied_paths == ["secrets/**"]


def test_invalid_policy_type_raises(tmp_path: Path) -> None:
    (tmp_path / "council.policy.yaml").write_text(
        "schema_version: 1\ndenied_commands: not-a-list\n",
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


def test_empty_file_is_rejected_as_unversioned(tmp_path: Path) -> None:
    (tmp_path / "council.policy.yaml").write_text("", encoding="utf-8")
    with pytest.raises(PolicyValidationError, match="schema_version: 1"):
        load_policy_file(tmp_path)


def test_legacy_unversioned_policy_is_rejected_with_migration(
    tmp_path: Path,
) -> None:
    path = tmp_path / "council.policy.yaml"
    path.write_text('denied_commands:\n  - "curl *"\n', encoding="utf-8")

    with pytest.raises(PolicyValidationError) as raised:
        load_policy_file(tmp_path)

    message = str(raised.value)
    assert str(path) in message
    assert "missing required field 'schema_version'" in message
    assert "schema_version: 1" in message


def test_unsupported_policy_version_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "council.policy.yaml").write_text(
        "schema_version: 2\n",
        encoding="utf-8",
    )

    with pytest.raises(PolicyValidationError, match="unsupported schema_version 2"):
        load_policy_file(tmp_path)


@pytest.mark.parametrize("value", ['"1"', "1.0", "true"])
def test_non_integer_policy_version_is_rejected(
    tmp_path: Path,
    value: str,
) -> None:
    (tmp_path / "council.policy.yaml").write_text(
        f"schema_version: {value}\n",
        encoding="utf-8",
    )

    with pytest.raises(
        PolicyValidationError,
        match="field 'schema_version' must be integer 1",
    ):
        load_policy_file(tmp_path)


def test_unknown_field_rejects_entire_policy(tmp_path: Path) -> None:
    (tmp_path / "council.policy.yaml").write_text(
        "\n".join(
            [
                "schema_version: 1",
                "denied_commands:",
                '  - "curl *"',
                "future_restriction: true",
                "",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(PolicyValidationError) as raised:
        load_policy_file(tmp_path)

    message = str(raised.value)
    assert "future_restriction" in message
    assert "Extra inputs are not permitted" in message


def test_misspelled_security_field_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "council.policy.yaml").write_text(
        "schema_version: 1\ndenied_command:\n  - \"curl *\"\n",
        encoding="utf-8",
    )

    with pytest.raises(PolicyValidationError, match="denied_command"):
        load_policy_file(tmp_path)


def test_authorization_field_error_does_not_echo_secret_value(
    tmp_path: Path,
) -> None:
    secret = "super-secret-grant-token"
    (tmp_path / "council.policy.yaml").write_text(
        f"schema_version: 1\ngrant: {secret}\n",
        encoding="utf-8",
    )

    with pytest.raises(PolicyValidationError) as raised:
        load_policy_file(tmp_path)

    message = str(raised.value)
    assert "grant" in message
    assert secret not in message


def test_deny_over_allow() -> None:
    policy = CouncilPolicy(
        schema_version=1,
        allowed_commands=["curl *"],
        denied_commands=["curl *"],
    )
    decision = evaluate_command("curl https://example.com", policy)
    assert decision.allowed is False
    assert decision.reason is PolicyCommandReason.DENIED
    assert decision.matched_pattern == "curl *"


def test_allowlist_refuses_non_matching() -> None:
    policy = CouncilPolicy(schema_version=1, allowed_commands=["pytest *"])
    decision = evaluate_command("echo hello", policy)
    assert decision.allowed is False
    assert decision.reason is PolicyCommandReason.NOT_ALLOWED


def test_allowlist_permits_matching() -> None:
    policy = CouncilPolicy(schema_version=1, allowed_commands=["pytest *"])
    decision = evaluate_command("pytest -q", policy)
    assert decision.allowed is True
    assert decision.reason is None


def test_empty_allowlist_no_restriction() -> None:
    policy = CouncilPolicy(
        schema_version=1,
        allowed_commands=[],
        denied_commands=[],
    )
    decision = evaluate_command("echo hello", policy)
    assert decision.allowed is True


def test_no_policy_allows_all() -> None:
    decision = evaluate_command("curl https://example.com", None)
    assert decision.allowed is True


def test_effective_denied_paths_union() -> None:
    policy = CouncilPolicy(
        schema_version=1,
        denied_paths=["secrets/**", ".env"],
    )
    paths = effective_denied_paths(policy)
    assert paths[0 : len(DEFAULT_DENIED_PATTERNS)] == DEFAULT_DENIED_PATTERNS
    assert "secrets/**" in paths
    assert paths.count(".env") == 1


def test_effective_denied_paths_without_policy() -> None:
    assert effective_denied_paths(None) == DEFAULT_DENIED_PATTERNS


def test_active_policy_context() -> None:
    policy = CouncilPolicy(schema_version=1, denied_commands=["sudo *"])
    assert get_active_policy() is None
    with active_policy(policy):
        assert get_active_policy() is policy
        decision = evaluate_command("sudo true")
        assert decision.allowed is False
    assert get_active_policy() is None
