"""Unit tests for the conservative ``run_tests`` argument parser."""

from __future__ import annotations

import pytest

from council_agent.security import CommandRejectionReason
from council_agent.tools.pytest_args import (
    ParsedPytestArgs,
    RejectedPytestArgs,
    parse_pytest_args,
)


@pytest.mark.parametrize(
    ("raw", "argv", "paths"),
    [
        ("", (), ()),
        ("-q -x", ("-q", "-x"), ()),
        ('-k "test with spaces"', ("-k", "test with spaces"), ()),
        ("-vv --maxfail=2 --tb short", ("-vv", "--maxfail=2", "--tb", "short"), ()),
        (
            "tests/unit/test_one.py::test_case tests/integration",
            ("tests/unit/test_one.py::test_case", "tests/integration"),
            ("tests/unit/test_one.py", "tests/integration"),
        ),
        ("-- -leading.py", ("--", "-leading.py"), ("-leading.py",)),
    ],
)
def test_parse_supported_pytest_args(
    raw: str,
    argv: tuple[str, ...],
    paths: tuple[str, ...],
) -> None:
    result = parse_pytest_args(raw)
    assert isinstance(result, ParsedPytestArgs)
    assert result.argv == argv
    assert result.path_operands == paths


@pytest.mark.parametrize(
    "raw",
    [
        "-q; touch marker",
        "-q && touch marker",
        "-q || touch marker",
        "-q | cat",
        "-q > result.txt",
        "-q\n-x",
        "-k `pwd`",
        "-k $(pwd)",
        '-k "$HOME"',
    ],
)
def test_parse_pytest_args_rejects_shell_control(raw: str) -> None:
    result = parse_pytest_args(raw)
    assert isinstance(result, RejectedPytestArgs)
    assert result.rejection_reason is CommandRejectionReason.SHELL_METACHAR


@pytest.mark.parametrize("raw", ['-k "unterminated', "\0"])
def test_parse_pytest_args_rejects_unparseable_input(raw: str) -> None:
    result = parse_pytest_args(raw)
    assert isinstance(result, RejectedPytestArgs)
    assert result.rejection_reason is CommandRejectionReason.UNPARSEABLE


@pytest.mark.parametrize(
    "raw",
    [
        "--unknown",
        "--basetemp elsewhere",
        "--junitxml=report.xml",
        "--maxfail",
        "--tb=",
    ],
)
def test_parse_pytest_args_rejects_unmodeled_options(raw: str) -> None:
    result = parse_pytest_args(raw)
    assert isinstance(result, RejectedPytestArgs)
    assert result.rejection_reason is CommandRejectionReason.UNSUPPORTED
