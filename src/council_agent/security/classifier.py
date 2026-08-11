"""Fail-closed analysis for the supported simple-command grammar."""

from __future__ import annotations

import shlex
from dataclasses import dataclass
from enum import Enum
from typing import TypeAlias


class CommandCategory(str, Enum):
    """Command risk category used by the classifier and run_command gate."""

    READ = "read"
    WRITE = "write"
    DANGEROUS = "dangerous"


@dataclass(frozen=True)
class ClassificationResult:
    """One accepted canonical command action."""

    argv: tuple[str, ...]
    category: CommandCategory
    matched_rule: str
    path_operands: tuple[str, ...] = ()

    @property
    def accepted(self) -> bool:
        return True


class CommandRejectionReason(str, Enum):
    """Stable reasons emitted before a command action exists."""

    UNSUPPORTED = "unsupported"
    UNPARSEABLE = "unparseable"
    SHELL_METACHAR = "shell_metachar"


@dataclass(frozen=True)
class RejectedCommandAnalysis:
    """A command refused before classification or execution."""

    rejection_reason: CommandRejectionReason
    error: str

    @property
    def accepted(self) -> bool:
        return False


CommandAnalysis: TypeAlias = ClassificationResult | RejectedCommandAnalysis

_SHELL_CONTROL_CHARS = frozenset(";|&`$()<> \r\n".replace(" ", ""))

_READ_COMMANDS = frozenset({"echo", "pwd", "cat", "ls"})
_WRITE_COMMANDS = frozenset({"rm", "mv", "cp", "touch", "mkdir"})
_DANGEROUS_COMMANDS = frozenset(
    {
        "sudo",
        "curl",
        "wget",
        "chmod",
        "chown",
        "mkfs",
        "dd",
        "shutdown",
        "reboot",
    }
)

_CAT_SHORT_OPTIONS = frozenset("AbeEnstTuv")
_CAT_LONG_OPTIONS = frozenset(
    {
        "--show-all",
        "--number-nonblank",
        "--show-ends",
        "--number",
        "--squeeze-blank",
        "--show-tabs",
        "--show-nonprinting",
        "--help",
        "--version",
    }
)
_LS_SHORT_OPTIONS = frozenset("aAbCdFfghHiklLmnopqRrSsTtuUvxX1")
_LS_LONG_OPTIONS = frozenset(
    {
        "--all",
        "--almost-all",
        "--directory",
        "--classify",
        "--file-type",
        "--human-readable",
        "--dereference-command-line",
        "--inode",
        "--numeric-uid-gid",
        "--reverse",
        "--recursive",
        "--size",
        "--help",
        "--version",
    }
)
_RM_SHORT_OPTIONS = frozenset("dfiIrvR")
_RM_LONG_OPTIONS = frozenset(
    {
        "--dir",
        "--force",
        "--interactive",
        "--one-file-system",
        "--no-preserve-root",
        "--preserve-root",
        "--recursive",
        "--verbose",
        "--help",
        "--version",
    }
)
_MV_SHORT_OPTIONS = frozenset("finv")
_MV_LONG_OPTIONS = frozenset(
    {"--force", "--interactive", "--no-clobber", "--verbose", "--help", "--version"}
)
_CP_SHORT_OPTIONS = frozenset("aHLPdfilnprRsv")
_CP_LONG_OPTIONS = frozenset(
    {
        "--archive",
        "--dereference",
        "--force",
        "--interactive",
        "--no-clobber",
        "--no-dereference",
        "--preserve",
        "--recursive",
        "--symbolic-link",
        "--verbose",
        "--help",
        "--version",
    }
)
_TOUCH_SHORT_OPTIONS = frozenset("acm")
_TOUCH_LONG_OPTIONS = frozenset(
    {"--no-create", "--help", "--version"}
)
_MKDIR_SHORT_OPTIONS = frozenset("pv")
_MKDIR_LONG_OPTIONS = frozenset(
    {"--parents", "--verbose", "--help", "--version"}
)


def contains_shell_control(value: str) -> bool:
    """Return whether raw text contains syntax outside the simple grammar."""

    return any(char in _SHELL_CONTROL_CHARS for char in value)


def _reject(reason: CommandRejectionReason, error: str) -> RejectedCommandAnalysis:
    return RejectedCommandAnalysis(rejection_reason=reason, error=error)


def _parse_options_and_operands(
    args: tuple[str, ...],
    *,
    short_options: frozenset[str],
    long_options: frozenset[str],
    minimum_operands: int,
) -> tuple[tuple[str, ...], tuple[str, ...]] | None:
    """Validate flag-only options and return options plus path operands."""

    options: list[str] = []
    operands: list[str] = []
    end_options = False

    for token in args:
        if not end_options and token == "--":
            end_options = True
            options.append(token)
            continue
        if not end_options and token.startswith("--"):
            if token not in long_options:
                return None
            options.append(token)
            continue
        if not end_options and token.startswith("-") and token != "-":
            if not token[1:] or any(char not in short_options for char in token[1:]):
                return None
            options.append(token)
            continue
        operands.append(token)

    if len(operands) < minimum_operands:
        return None
    return tuple(options), tuple(operands)


def _analyze_path_command(argv: tuple[str, ...]) -> CommandAnalysis:
    executable = argv[0]
    schemas = {
        "cat": (_CAT_SHORT_OPTIONS, _CAT_LONG_OPTIONS, 0),
        "ls": (_LS_SHORT_OPTIONS, _LS_LONG_OPTIONS, 0),
        "rm": (_RM_SHORT_OPTIONS, _RM_LONG_OPTIONS, 1),
        "mv": (_MV_SHORT_OPTIONS, _MV_LONG_OPTIONS, 2),
        "cp": (_CP_SHORT_OPTIONS, _CP_LONG_OPTIONS, 2),
        "touch": (_TOUCH_SHORT_OPTIONS, _TOUCH_LONG_OPTIONS, 1),
        "mkdir": (_MKDIR_SHORT_OPTIONS, _MKDIR_LONG_OPTIONS, 1),
    }
    short_options, long_options, minimum_operands = schemas[executable]
    parsed = _parse_options_and_operands(
        argv[1:],
        short_options=short_options,
        long_options=long_options,
        minimum_operands=minimum_operands,
    )
    if parsed is None:
        return _reject(
            CommandRejectionReason.UNSUPPORTED,
            f"Unsupported or ambiguous {executable} command form",
        )

    options, operands = parsed
    category = (
        CommandCategory.READ if executable in _READ_COMMANDS else CommandCategory.WRITE
    )
    matched_rule = executable
    if executable == "rm" and (
        any(
            option in {"--force", "--recursive"}
            or (
                option.startswith("-")
                and not option.startswith("--")
                and any(char in "fRr" for char in option[1:])
            )
            for option in options
        )
    ):
        category = CommandCategory.DANGEROUS
        matched_rule = "rm-force-or-recursive"

    return ClassificationResult(
        argv=argv,
        category=category,
        matched_rule=matched_rule,
        path_operands=operands,
    )


def _analyze_pwd(argv: tuple[str, ...]) -> CommandAnalysis:
    if any(token not in {"-L", "-P", "--help", "--version"} for token in argv[1:]):
        return _reject(
            CommandRejectionReason.UNSUPPORTED,
            "Unsupported pwd command form",
        )
    return ClassificationResult(
        argv=argv,
        category=CommandCategory.READ,
        matched_rule="pwd",
    )


def classify_command(command: str) -> CommandAnalysis:
    """Analyze one supported simple command into an immutable canonical action."""

    if not command or not command.strip() or "\0" in command:
        return _reject(
            CommandRejectionReason.UNPARSEABLE,
            "Command is empty or contains NUL",
        )
    if contains_shell_control(command):
        return _reject(
            CommandRejectionReason.SHELL_METACHAR,
            "Shell control syntax is not supported",
        )

    try:
        parsed = shlex.split(command, posix=True)
    except ValueError as exc:
        return _reject(CommandRejectionReason.UNPARSEABLE, f"Cannot parse command: {exc}")

    if not parsed:
        return _reject(CommandRejectionReason.UNPARSEABLE, "Command is empty")

    argv = tuple(parsed)
    executable = argv[0]
    if "/" in executable or "\\" in executable:
        return _reject(
            CommandRejectionReason.UNSUPPORTED,
            "Path-qualified executables are not supported",
        )

    if executable in {"cat", "ls", "rm", "mv", "cp", "touch", "mkdir"}:
        return _analyze_path_command(argv)
    if executable == "pwd":
        return _analyze_pwd(argv)
    if executable == "echo":
        return ClassificationResult(
            argv=argv,
            category=CommandCategory.READ,
            matched_rule="echo",
        )
    if executable in _DANGEROUS_COMMANDS:
        return ClassificationResult(
            argv=argv,
            category=CommandCategory.DANGEROUS,
            matched_rule=executable,
        )

    return _reject(
        CommandRejectionReason.UNSUPPORTED,
        f"Unsupported executable: {executable}",
    )
