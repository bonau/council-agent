"""Unit tests for confirmation modes and gate."""

from __future__ import annotations

from council_agent.security import (
    ActionKind,
    ConfirmationOutcome,
    ConfirmMode,
    confirmation_policy,
    get_confirmation_policy,
    require_confirmation,
    resolve_cli_confirm_mode,
)


def test_default_mode_is_compat() -> None:
    assert get_confirmation_policy().mode is ConfirmMode.COMPAT


def test_resolve_cli_modes() -> None:
    assert resolve_cli_confirm_mode(yes=True, is_tty=False) is ConfirmMode.AUTO
    assert resolve_cli_confirm_mode(yes=True, is_tty=True) is ConfirmMode.AUTO
    assert resolve_cli_confirm_mode(yes=False, is_tty=True) is ConfirmMode.ASK
    assert resolve_cli_confirm_mode(yes=False, is_tty=False) is ConfirmMode.REFUSE


def test_auto_allows_without_prompt() -> None:
    calls: list[str] = []

    def confirm_fn(message: str) -> bool:
        calls.append(message)
        return False

    with confirmation_policy(ConfirmMode.AUTO, confirm_fn=confirm_fn):
        result = require_confirmation(ActionKind.DANGEROUS_SHELL, "curl x")

    assert result.allowed is True
    assert result.outcome is ConfirmationOutcome.AUTO
    assert calls == []


def test_refuse_denies_without_prompt() -> None:
    calls: list[str] = []

    def confirm_fn(message: str) -> bool:
        calls.append(message)
        return True

    with confirmation_policy(ConfirmMode.REFUSE, confirm_fn=confirm_fn):
        result = require_confirmation(ActionKind.WRITE_FILE, "a.txt")

    assert result.allowed is False
    assert result.outcome is ConfirmationOutcome.REFUSED
    assert calls == []


def test_ask_approves_on_yes() -> None:
    with confirmation_policy(ConfirmMode.ASK, confirm_fn=lambda _m: True):
        result = require_confirmation(ActionKind.WRITE_SHELL, "mkdir foo")

    assert result.allowed is True
    assert result.outcome is ConfirmationOutcome.APPROVED


def test_ask_denies_on_no() -> None:
    with confirmation_policy(ConfirmMode.ASK, confirm_fn=lambda _m: False):
        result = require_confirmation(ActionKind.DELETE_FILE, "a.txt")

    assert result.allowed is False
    assert result.outcome is ConfirmationOutcome.DENIED


def test_compat_refuses_dangerous_without_prompt() -> None:
    calls: list[str] = []

    with confirmation_policy(ConfirmMode.COMPAT, confirm_fn=lambda m: calls.append(m) or True):
        result = require_confirmation(ActionKind.DANGEROUS_SHELL, "sudo ls")

    assert result.allowed is False
    assert result.outcome is ConfirmationOutcome.REFUSED
    assert calls == []


def test_compat_allows_write_without_prompt() -> None:
    calls: list[str] = []

    with confirmation_policy(ConfirmMode.COMPAT, confirm_fn=lambda m: calls.append(m) or False):
        write_shell = require_confirmation(ActionKind.WRITE_SHELL, "mkdir x")
        write_file = require_confirmation(ActionKind.WRITE_FILE, "a.txt")
        delete_file = require_confirmation(ActionKind.DELETE_FILE, "a.txt")

    assert write_shell.allowed is True
    assert write_shell.outcome is ConfirmationOutcome.COMPAT_ALLOW
    assert write_file.allowed is True
    assert delete_file.allowed is True
    assert calls == []


def test_policy_context_resets() -> None:
    assert get_confirmation_policy().mode is ConfirmMode.COMPAT
    with confirmation_policy(ConfirmMode.AUTO):
        assert get_confirmation_policy().mode is ConfirmMode.AUTO
    assert get_confirmation_policy().mode is ConfirmMode.COMPAT
