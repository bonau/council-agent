"""Tests for run_tests tool and pytest output parsing."""

from pathlib import Path

from council_agent.tools.shell import parse_pytest_output, run_tests


def test_parse_pytest_output_all_passed() -> None:
    output = "...\n\n3 passed in 0.12s"
    parsed = parse_pytest_output(output, exit_code=0)
    assert parsed["passed"] == 3
    assert parsed["failed"] == 0
    assert parsed["skipped"] == 0
    assert parsed["exit_code"] == 0


def test_parse_pytest_output_with_failures() -> None:
    output = (
        "FAILED tests/test_x.py::test_bad - AssertionError\n"
        "E   assert False\n"
        "1 failed, 2 passed in 0.05s"
    )
    parsed = parse_pytest_output(output, exit_code=1)
    assert parsed["passed"] == 2
    assert parsed["failed"] == 1
    assert len(parsed["failures"]) >= 1


def test_run_tests_all_pass(workspace_root: Path) -> None:
    tests_dir = workspace_root / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_ok.py").write_text(
        "def test_one():\n    assert 1 + 1 == 2\n",
        encoding="utf-8",
    )

    result = run_tests(path="tests")
    assert result.success
    assert result.metadata["exit_code"] == 0
    assert result.metadata["passed"] >= 1
    assert result.metadata["failed"] == 0


def test_run_tests_with_failure(workspace_root: Path) -> None:
    tests_dir = workspace_root / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_bad.py").write_text(
        "def test_fail():\n    assert False\n",
        encoding="utf-8",
    )

    result = run_tests(path="tests")
    assert not result.success
    assert result.metadata["exit_code"] != 0
    assert result.metadata["failed"] >= 1
    assert result.metadata["failures"]


def test_run_tests_with_skip(workspace_root: Path) -> None:
    tests_dir = workspace_root / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_skip.py").write_text(
        "import pytest\n\n@pytest.mark.skip\n"
        "def test_skipped():\n    assert False\n",
        encoding="utf-8",
    )

    result = run_tests(path="tests")
    assert result.success
    assert result.metadata["skipped"] >= 1


def test_run_tests_nonexistent_path() -> None:
    result = run_tests(path="does_not_exist")
    assert not result.success
    assert result.error is not None
