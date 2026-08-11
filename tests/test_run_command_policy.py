"""Integration tests: run_command + project policy gates."""

from __future__ import annotations

from pathlib import Path
from unittest import mock

from council_agent.security import (
    ConfirmMode,
    CouncilPolicy,
    active_policy,
    confirmation_policy,
)
from council_agent.tools.shell import run_command


def test_policy_denied_command_does_not_run() -> None:
    policy = CouncilPolicy(denied_commands=["curl *"])
    with mock.patch("council_agent.tools.shell.subprocess.run") as run_mock:
        with active_policy(policy):
            result = run_command("curl https://example.com")

    assert result.success is False
    assert result.error is not None
    assert "policy" in result.error.lower()
    assert result.metadata.get("policy_decision") == "denied"
    assert result.metadata.get("policy_pattern") == "curl *"
    assert "exit_code" not in result.metadata
    run_mock.assert_not_called()


def test_policy_allowlist_refuses_other_commands() -> None:
    policy = CouncilPolicy(allowed_commands=["pytest *"])
    with mock.patch("council_agent.tools.shell.subprocess.run") as run_mock:
        with active_policy(policy):
            result = run_command("echo hello")

    assert result.success is False
    assert result.metadata.get("policy_decision") == "not_allowed"
    run_mock.assert_not_called()


def test_policy_allowlist_permits_matching_read_command() -> None:
    policy = CouncilPolicy(allowed_commands=["echo *"])
    with active_policy(policy):
        result = run_command("echo hello")

    assert result.success is True
    assert result.output == "hello"
    assert result.metadata.get("classification") == "read"


def test_policy_check_precedes_confirmation_prompt() -> None:
    """Denied-by-policy dangerous command must not invoke confirmation."""
    policy = CouncilPolicy(denied_commands=["curl *"])
    confirm_calls: list[str] = []

    def _confirm(message: str) -> bool:
        confirm_calls.append(message)
        return True

    with mock.patch("council_agent.tools.shell.subprocess.run") as run_mock:
        with active_policy(policy):
            with confirmation_policy(ConfirmMode.ASK, confirm_fn=_confirm):
                result = run_command("curl https://example.com")

    assert result.success is False
    assert result.metadata.get("policy_decision") == "denied"
    assert confirm_calls == []
    run_mock.assert_not_called()


def test_policy_allowed_dangerous_still_needs_confirmation() -> None:
    policy = CouncilPolicy(allowed_commands=["curl *"])
    with mock.patch("council_agent.tools.shell.subprocess.run") as run_mock:
        with active_policy(policy):
            with confirmation_policy(ConfirmMode.REFUSE):
                result = run_command("curl https://example.com")

    assert result.success is False
    assert result.metadata.get("classification") == "dangerous"
    assert result.metadata.get("confirmation") == "refused"
    assert "policy_decision" not in result.metadata
    run_mock.assert_not_called()


def test_no_active_policy_unchanged(tmp_path: Path) -> None:
    result = run_command("echo hello", cwd=str(tmp_path))
    assert result.success is True
    assert result.output == "hello"
