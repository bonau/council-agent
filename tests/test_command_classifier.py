"""Table-driven tests for fail-closed command analysis."""

from __future__ import annotations

import pytest

from council_agent.security import (
    ClassificationResult,
    CommandCategory,
    CommandRejectionReason,
    RejectedCommandAnalysis,
    classify_command,
)


@pytest.mark.parametrize(
    ("command", "argv", "rule"),
    [
        ("echo hello", ("echo", "hello"), "echo"),
        ('echo "hello world"', ("echo", "hello world"), "echo"),
        ("pwd -P", ("pwd", "-P"), "pwd"),
        ("ls", ("ls",), "ls"),
        ("cat README.md", ("cat", "README.md"), "cat"),
    ],
)
def test_read_commands(
    command: str,
    argv: tuple[str, ...],
    rule: str,
) -> None:
    result = classify_command(command)
    assert isinstance(result, ClassificationResult)
    assert result.argv == argv
    assert result.category is CommandCategory.READ
    assert result.matched_rule == rule


@pytest.mark.parametrize(
    ("command", "rule"),
    [
        ("mkdir foo", "mkdir"),
        ("touch a.txt", "touch"),
        ("mv a b", "mv"),
        ("cp a b", "cp"),
        ("rm file.txt", "rm"),
    ],
)
def test_write_commands(command: str, rule: str) -> None:
    result = classify_command(command)
    assert isinstance(result, ClassificationResult)
    assert result.category is CommandCategory.WRITE
    assert result.matched_rule == rule


@pytest.mark.parametrize(
    ("command", "rule"),
    [
        ("sudo apt update", "sudo"),
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
    assert isinstance(result, ClassificationResult)
    assert result.category is CommandCategory.DANGEROUS
    assert result.matched_rule == rule


def test_dangerous_takes_precedence_over_write() -> None:
    result = classify_command("sudo mkdir /opt/x")
    assert isinstance(result, ClassificationResult)
    assert result.category is CommandCategory.DANGEROUS
    assert result.matched_rule == "sudo"


def test_sudo_matched_rule_non_empty() -> None:
    result = classify_command("sudo true")
    assert isinstance(result, ClassificationResult)
    assert result.category is CommandCategory.DANGEROUS
    assert result.matched_rule
    assert isinstance(result.matched_rule, str)


@pytest.mark.parametrize(
    "command",
    [
        "python -m pytest",
        "uv run pytest",
        "tee out.txt",
        "SUDO ls",
        "/bin/cat README.md",
        "sh -c pwd",
        "bash -c pwd",
    ],
)
def test_unknown_or_unsupported_executable_fails_closed(command: str) -> None:
    result = classify_command(command)
    assert isinstance(result, RejectedCommandAnalysis)
    assert result.rejection_reason is CommandRejectionReason.UNSUPPORTED


@pytest.mark.parametrize(
    "command",
    [
        "echo ok; touch marker",
        "echo ok | cat",
        "echo ok && touch marker",
        "echo ok || touch marker",
        "echo ok &",
        "echo `pwd`",
        "echo $(pwd)",
        "echo < input",
        "echo > output",
        "echo first\nmkdir marker",
        "echo first\rmkdir marker",
        'echo "$HOME"',
        'echo "("',
    ],
)
def test_all_shell_control_forms_are_rejected(command: str) -> None:
    result = classify_command(command)
    assert isinstance(result, RejectedCommandAnalysis)
    assert result.rejection_reason is CommandRejectionReason.SHELL_METACHAR


@pytest.mark.parametrize("command", ["", "  ", "\0", 'echo "unterminated'])
def test_unparseable_input_is_rejected(command: str) -> None:
    result = classify_command(command)
    assert isinstance(result, RejectedCommandAnalysis)
    assert result.rejection_reason is CommandRejectionReason.UNPARSEABLE


@pytest.mark.parametrize(
    ("command", "operands"),
    [
        ("cat -- -notes", ("-notes",)),
        ("ls -la docs README.md", ("docs", "README.md")),
        ("rm -- -old", ("-old",)),
        ("mv one two dest", ("one", "two", "dest")),
        ("cp -R source another destination", ("source", "another", "destination")),
        ("touch first second", ("first", "second")),
        ("mkdir -p one/two", ("one/two",)),
    ],
)
def test_path_operand_adapters(command: str, operands: tuple[str, ...]) -> None:
    result = classify_command(command)
    assert isinstance(result, ClassificationResult)
    assert result.path_operands == operands


@pytest.mark.parametrize(
    "command",
    [
        "cat --color file",
        "ls --ignore pattern .",
        "rm --target-directory out source",
        "mv -t out source",
        "cp --target-directory=out source",
        "touch --reference source target",
        "mkdir --mode 755 target",
        "mv source",
        "cp source",
        "rm",
        "touch",
        "mkdir",
    ],
)
def test_ambiguous_or_unmodeled_command_forms_are_rejected(command: str) -> None:
    result = classify_command(command)
    assert isinstance(result, RejectedCommandAnalysis)
    assert result.rejection_reason is CommandRejectionReason.UNSUPPORTED
