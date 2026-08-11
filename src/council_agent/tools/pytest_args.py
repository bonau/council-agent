"""Pure parser for the conservative ``run_tests`` argument schema."""

from __future__ import annotations

import shlex
from dataclasses import dataclass
from typing import TypeAlias

from council_agent.security.classifier import (
    CommandRejectionReason,
    contains_shell_control,
)


@dataclass(frozen=True)
class ParsedPytestArgs:
    """Accepted pytest arguments and the path-bearing selectors they contain."""

    argv: tuple[str, ...]
    path_operands: tuple[str, ...]

    @property
    def accepted(self) -> bool:
        return True


@dataclass(frozen=True)
class RejectedPytestArgs:
    """Pytest arguments refused before a test process can be prepared."""

    rejection_reason: CommandRejectionReason
    error: str

    @property
    def accepted(self) -> bool:
        return False


PytestArgsAnalysis: TypeAlias = ParsedPytestArgs | RejectedPytestArgs

_FLAG_OPTIONS = frozenset(
    {
        "-q",
        "-x",
        "-s",
        "--quiet",
        "--exitfirst",
        "--collect-only",
        "--co",
        "--strict-config",
        "--strict-markers",
        "--disable-warnings",
        "--no-header",
        "--no-summary",
    }
)
_VALUE_OPTIONS = frozenset({"-k", "-m", "--maxfail", "--tb"})
_LONG_VALUE_PREFIXES = ("--maxfail=", "--tb=")


def _reject(
    reason: CommandRejectionReason,
    error: str,
) -> RejectedPytestArgs:
    return RejectedPytestArgs(rejection_reason=reason, error=error)


def _selector_path(token: str) -> str:
    """Return the filesystem portion of a pytest node selector."""

    return token.split("::", 1)[0]


def parse_pytest_args(args: str) -> PytestArgsAnalysis:
    """Parse supported pytest args once, refusing unknown or shell-like forms."""

    if "\0" in args:
        return _reject(
            CommandRejectionReason.UNPARSEABLE,
            "Pytest arguments contain NUL",
        )
    if contains_shell_control(args):
        return _reject(
            CommandRejectionReason.SHELL_METACHAR,
            "Shell control syntax is not supported in pytest arguments",
        )

    try:
        parsed = tuple(shlex.split(args, posix=True))
    except ValueError as exc:
        return _reject(
            CommandRejectionReason.UNPARSEABLE,
            f"Cannot parse pytest arguments: {exc}",
        )

    paths: list[str] = []
    index = 0
    end_options = False
    while index < len(parsed):
        token = parsed[index]
        if not end_options and token == "--":
            end_options = True
            index += 1
            continue

        if not end_options and token in _FLAG_OPTIONS:
            index += 1
            continue
        if not end_options and token.startswith("-v") and set(token[1:]) == {"v"}:
            index += 1
            continue
        if not end_options and token in _VALUE_OPTIONS:
            if index + 1 >= len(parsed):
                return _reject(
                    CommandRejectionReason.UNSUPPORTED,
                    f"Missing value for pytest option: {token}",
                )
            index += 2
            continue
        if not end_options and token.startswith(_LONG_VALUE_PREFIXES):
            if token.endswith("="):
                return _reject(
                    CommandRejectionReason.UNSUPPORTED,
                    f"Missing value for pytest option: {token}",
                )
            index += 1
            continue
        if not end_options and (
            (token.startswith("-k") and token != "-k")
            or (token.startswith("-m") and token != "-m")
        ):
            index += 1
            continue
        if not end_options and token.startswith("-"):
            return _reject(
                CommandRejectionReason.UNSUPPORTED,
                f"Unsupported pytest option: {token}",
            )

        path = _selector_path(token)
        if not path:
            return _reject(
                CommandRejectionReason.UNSUPPORTED,
                f"Unsupported pytest selector: {token}",
            )
        paths.append(path)
        index += 1

    return ParsedPytestArgs(argv=parsed, path_operands=tuple(paths))
