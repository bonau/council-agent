"""Unit tests for command classifier."""

from __future__ import annotations

import pytest

from council_agent.security import CommandCategory, classify_command


@pytest.mark.parametrize(
    "command",
    [
        "echo hello",
        "ls",
        "cat README.md",
        "python -m pytest",
        "python -m pytest tests/ -q",
        "uv run pytest",
    ],
)
def test_read_commands(command: str) -> None:
    result = classify_command(command)
    assert result.category is CommandCategory.READ
    assert result.matched_rule is None


@pytest.mark.parametrize(
    ("command", "rule"),
    [
        ("mkdir foo", "mkdir"),
        ("touch a.txt", "touch"),
        ("mv a b", "mv"),
        ("cp a b", "cp"),
        ("tee out.txt", "tee"),
        ("rm file.txt", "rm"),
        ("echo hi > out.txt", "shell-redirect"),
    ],
)
def test_write_commands(command: str, rule: str) -> None:
    result = classify_command(command)
    assert result.category is CommandCategory.WRITE
    assert result.matched_rule == rule


@pytest.mark.parametrize(
    ("command", "rule"),
    [
        ("sudo apt update", "sudo"),
        ("SUDO ls", "sudo"),
        ("curl https://example.com", "curl"),
        ("wget https://example.com", "wget"),
        ("chmod 777 file", "chmod"),
        ("chown user file", "chown"),
        ("rm -rf build", "rm-force-or-recursive"),
        ("rm -fr /tmp/x", "rm-force-or-recursive"),
        ("rm -r -f build", "rm-force-or-recursive"),
        ("mkfs /dev/sda", "mkfs"),
        ("dd if=/dev/zero of=/dev/sda", "dd"),
        ("shutdown -h now", "shutdown"),
        ("reboot", "reboot"),
    ],
)
def test_dangerous_commands(command: str, rule: str) -> None:
    result = classify_command(command)
    assert result.category is CommandCategory.DANGEROUS
    assert result.matched_rule == rule


def test_dangerous_takes_precedence_over_write() -> None:
    # Contains both mkdir (write) and sudo (dangerous)
    result = classify_command("sudo mkdir /opt/x")
    assert result.category is CommandCategory.DANGEROUS
    assert result.matched_rule == "sudo"


def test_sudo_matched_rule_non_empty() -> None:
    result = classify_command("sudo true")
    assert result.category is CommandCategory.DANGEROUS
    assert result.matched_rule
    assert isinstance(result.matched_rule, str)
