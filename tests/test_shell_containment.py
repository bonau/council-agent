"""Integration and no-side-effect coverage for shell containment."""

from __future__ import annotations

import shlex
import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest

from council_agent.security import (
    ConfirmMode,
    ConfirmationOutcome,
    ConfirmationResult,
    CouncilPolicy,
    PolicyCommandDecision,
    active_policy,
    confirmation_policy,
)
from council_agent.security.classifier import classify_command as analyze_command
from council_agent.tools.shell import run_command, run_tests


def _completed(stdout: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=[], returncode=0, stdout=stdout, stderr="")


def test_run_command_submits_resolved_argv_with_shell_false(tmp_path: Path) -> None:
    with (
        mock.patch(
            "council_agent.tools.shell.shutil.which",
            return_value="/trusted/bin/echo",
        ),
        mock.patch(
            "council_agent.tools.shell.subprocess.run",
            return_value=_completed("hello world\n"),
        ) as run_mock,
    ):
        result = run_command('echo "hello world"', cwd=str(tmp_path))

    assert result.success
    run_mock.assert_called_once_with(
        ["/trusted/bin/echo", "hello world"],
        shell=False,
        capture_output=True,
        text=True,
        cwd=str(tmp_path.resolve()),
        timeout=120,
    )


def test_run_command_gate_order_is_fixed(tmp_path: Path) -> None:
    events: list[str] = []

    class RecordingGuard:
        root = tmp_path.resolve()

        def resolve_cwd(self, cwd: str | None) -> Path:
            events.append("cwd")
            return self.root

        def resolve_from(self, cwd: Path, operand: str) -> Path:
            events.append(f"operand:{operand}")
            return cwd / operand

    def analyze(command: str):
        events.append("analysis")
        return analyze_command(command)

    def resolve_executable(executable: str) -> str:
        events.append("executable")
        return f"/trusted/{executable}"

    def evaluate(command: str) -> PolicyCommandDecision:
        events.append(f"policy:{command}")
        return PolicyCommandDecision(allowed=True)

    def confirm(*_args: object) -> ConfirmationResult:
        events.append("confirmation")
        return ConfirmationResult(allowed=True, outcome=ConfirmationOutcome.AUTO)

    def execute(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        events.append("execution")
        return _completed()

    with (
        mock.patch(
            "council_agent.tools.shell.get_workspace_guard",
            return_value=RecordingGuard(),
        ),
        mock.patch("council_agent.tools.shell.classify_command", side_effect=analyze),
        mock.patch(
            "council_agent.tools.shell.shutil.which",
            side_effect=resolve_executable,
        ),
        mock.patch(
            "council_agent.tools.shell.evaluate_command_policy",
            side_effect=evaluate,
        ),
        mock.patch(
            "council_agent.tools.shell.require_confirmation",
            side_effect=confirm,
        ),
        mock.patch(
            "council_agent.tools.shell.subprocess.run",
            side_effect=execute,
        ),
    ):
        result = run_command("mkdir target")

    assert result.success
    assert events == [
        "cwd",
        "analysis",
        "operand:target",
        "executable",
        "policy:mkdir target",
        "confirmation",
        "execution",
    ]


@pytest.mark.parametrize(
    ("command", "reason"),
    [
        ("unknown-tool arg", "unsupported"),
        ('echo "unterminated', "unparseable"),
        ("echo ok; touch marker", "shell_metachar"),
        ("echo ok | cat", "shell_metachar"),
        ("echo ok && touch marker", "shell_metachar"),
        ("echo `pwd`", "shell_metachar"),
        ("echo $(pwd)", "shell_metachar"),
    ],
)
def test_parser_refusals_never_start_subprocess(command: str, reason: str) -> None:
    with mock.patch("council_agent.tools.shell.subprocess.run") as run_mock:
        result = run_command(command)

    assert not result.success
    assert result.metadata == {"rejection_reason": reason}
    assert "exit_code" not in result.metadata
    run_mock.assert_not_called()


def test_policy_uses_canonical_quoting_and_execution_uses_same_args() -> None:
    policy = CouncilPolicy(allowed_commands=["echo 'hello world'"])
    with (
        active_policy(policy),
        mock.patch(
            "council_agent.tools.shell.shutil.which",
            return_value="/trusted/echo",
        ),
        mock.patch(
            "council_agent.tools.shell.subprocess.run",
            return_value=_completed("hello world\n"),
        ) as run_mock,
    ):
        result = run_command('echo "hello world"')

    assert result.success
    assert run_mock.call_args.args[0] == ["/trusted/echo", "hello world"]


def test_policy_denial_precedes_confirmation_for_canonical_action() -> None:
    policy = CouncilPolicy(denied_commands=["mkdir *"])
    with (
        active_policy(policy),
        mock.patch(
            "council_agent.tools.shell.require_confirmation"
        ) as confirm_mock,
        mock.patch("council_agent.tools.shell.subprocess.run") as run_mock,
    ):
        result = run_command("mkdir target")

    assert not result.success
    assert result.metadata["policy_decision"] == "denied"
    confirm_mock.assert_not_called()
    run_mock.assert_not_called()


def test_required_path_commands_execute_inside_workspace(tmp_path: Path) -> None:
    nested = tmp_path / "nested"
    nested.mkdir()

    assert run_command('mkdir "dir one"', cwd=str(nested)).success
    assert run_command('touch "dir one/source.txt"', cwd=str(nested)).success
    source = nested / "dir one" / "source.txt"
    source.write_text("payload", encoding="utf-8")

    assert run_command('cp "dir one/source.txt" copy.txt', cwd=str(nested)).success
    assert run_command("mv copy.txt moved.txt", cwd=str(nested)).success
    cat_result = run_command("cat moved.txt", cwd=str(nested))
    assert cat_result.success
    assert cat_result.output == "payload"
    ls_result = run_command("ls moved.txt", cwd=str(nested))
    assert ls_result.success
    assert "moved.txt" in ls_result.output
    assert run_command("rm moved.txt", cwd=str(nested)).success
    assert not (nested / "moved.txt").exists()

    absolute = nested / "absolute.txt"
    assert run_command(f"touch {shlex.quote(str(absolute))}").success
    assert absolute.exists()


def test_path_beginning_with_dash_executes_after_double_dash(tmp_path: Path) -> None:
    assert run_command("touch -- -note", cwd=str(tmp_path)).success
    (tmp_path / "-note").write_text("dash", encoding="utf-8")
    result = run_command("cat -- -note", cwd=str(tmp_path))
    assert result.success
    assert result.output == "dash"


@pytest.mark.parametrize("executable", ["cat", "python"])
def test_external_sentinel_read_is_refused(
    tmp_path: Path,
    executable: str,
) -> None:
    outside = tmp_path.parent / f"{tmp_path.name}-{executable}-sentinel.txt"
    outside.write_text("unchanged", encoding="utf-8")
    command = f"{executable} {shlex.quote(str(outside))}"
    try:
        with mock.patch("council_agent.tools.shell.subprocess.run") as run_mock:
            result = run_command(command)
        assert not result.success
        assert result.metadata["rejection_reason"] in {
            "unsupported",
            "workspace_boundary",
        }
        assert outside.read_text(encoding="utf-8") == "unchanged"
        run_mock.assert_not_called()
    finally:
        outside.unlink(missing_ok=True)


@pytest.mark.parametrize("command_name", ["cp", "mv"])
def test_external_destination_is_refused_without_side_effect(
    tmp_path: Path,
    command_name: str,
) -> None:
    source = tmp_path / "source.txt"
    source.write_text("source", encoding="utf-8")
    outside = tmp_path.parent / f"{tmp_path.name}-{command_name}-outside.txt"
    outside.write_text("sentinel", encoding="utf-8")
    command = f"{command_name} source.txt {shlex.quote(str(outside))}"
    try:
        with mock.patch("council_agent.tools.shell.subprocess.run") as run_mock:
            result = run_command(command)
        assert not result.success
        assert result.metadata["rejection_reason"] == "workspace_boundary"
        assert source.read_text(encoding="utf-8") == "source"
        assert outside.read_text(encoding="utf-8") == "sentinel"
        run_mock.assert_not_called()
    finally:
        outside.unlink(missing_ok=True)


def test_one_invalid_operand_refuses_entire_multi_source_action(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.txt"
    source.write_text("source", encoding="utf-8")
    outside = tmp_path.parent / f"{tmp_path.name}-mixed-outside.txt"
    outside.write_text("sentinel", encoding="utf-8")
    try:
        command = f"cp source.txt good.txt {shlex.quote(str(outside))}"
        with mock.patch("council_agent.tools.shell.subprocess.run") as run_mock:
            result = run_command(command)
        assert not result.success
        assert not (tmp_path / "good.txt").exists()
        assert outside.read_text(encoding="utf-8") == "sentinel"
        run_mock.assert_not_called()
    finally:
        outside.unlink(missing_ok=True)


def test_traversal_and_symlink_escape_leave_external_sentinel_unchanged(
    tmp_path: Path,
) -> None:
    nested = tmp_path / "nested"
    nested.mkdir()
    outside = tmp_path.parent / f"{tmp_path.name}-escape-sentinel.txt"
    outside.write_text("sentinel", encoding="utf-8")
    link = nested / "escape"
    link.symlink_to(outside)
    try:
        for operand in ("../../escape-sentinel.txt", "escape"):
            with mock.patch("council_agent.tools.shell.subprocess.run") as run_mock:
                result = run_command(f"cat {operand}", cwd=str(nested))
            assert not result.success
            assert result.metadata["rejection_reason"] == "workspace_boundary"
            run_mock.assert_not_called()
        assert outside.read_text(encoding="utf-8") == "sentinel"
    finally:
        link.unlink(missing_ok=True)
        outside.unlink(missing_ok=True)


def test_denied_path_has_stable_reason_and_no_process(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("SECRET=1", encoding="utf-8")
    with mock.patch("council_agent.tools.shell.subprocess.run") as run_mock:
        result = run_command("cat .env")
    assert not result.success
    assert result.metadata["rejection_reason"] == "denied_path"
    assert "exit_code" not in result.metadata
    run_mock.assert_not_called()


@pytest.mark.parametrize(
    "command",
    [
        "echo ok; touch marker",
        "echo ok && touch marker",
        "echo ok || touch marker",
        "echo ok | touch marker",
        "echo ok > marker",
        "echo ok\ntouch marker",
        "`touch marker`",
        "$(touch marker)",
        "curl https://example.com; touch marker",
    ],
)
def test_compound_syntax_has_no_file_process_or_network_side_effect(
    tmp_path: Path,
    command: str,
) -> None:
    marker = tmp_path / "marker"
    with mock.patch("council_agent.tools.shell.subprocess.run") as run_mock:
        result = run_command(command)
    assert not result.success
    assert result.metadata["rejection_reason"] == "shell_metachar"
    assert not marker.exists()
    run_mock.assert_not_called()


def test_inherited_environment_value_cannot_be_expanded(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    outside = tmp_path.parent / f"{tmp_path.name}-environment-sentinel.txt"
    outside.write_text("sentinel", encoding="utf-8")
    monkeypatch.setenv("SENTINEL_PATH", str(outside))
    try:
        with mock.patch("council_agent.tools.shell.subprocess.run") as run_mock:
            result = run_command("cat $SENTINEL_PATH")
        assert not result.success
        assert result.metadata["rejection_reason"] == "shell_metachar"
        assert outside.read_text(encoding="utf-8") == "sentinel"
        run_mock.assert_not_called()
    finally:
        outside.unlink(missing_ok=True)


def test_run_tests_preserves_path_and_quoted_arg_boundaries(tmp_path: Path) -> None:
    tests_dir = tmp_path / "tests with spaces"
    tests_dir.mkdir()
    with mock.patch(
        "council_agent.tools.shell.subprocess.run",
        return_value=_completed("1 passed in 0.01s\n"),
    ) as run_mock:
        result = run_tests(
            path=str(tests_dir),
            args='-k "test with spaces" -vv',
        )

    assert result.success
    submitted = run_mock.call_args.args[0]
    assert submitted == [
        sys.executable,
        "-m",
        "pytest",
        str(tests_dir.resolve()),
        "-q",
        "--tb=line",
        "-k",
        "test with spaces",
        "-vv",
    ]
    assert run_mock.call_args.kwargs["shell"] is False


def test_run_tests_executes_typed_special_character_path(tmp_path: Path) -> None:
    tests_dir = tmp_path / "suite ;$()`' 空白"
    tests_dir.mkdir()
    (tests_dir / "test_ok.py").write_text(
        "def test_ok():\n    assert True\n",
        encoding="utf-8",
    )
    result = run_tests(path=str(tests_dir))
    assert result.success
    assert result.metadata["passed"] == 1


@pytest.mark.parametrize(
    "args",
    [
        "-q; touch marker",
        "-q && touch marker",
        "-q || touch marker",
        "-q | touch marker",
        "-q > marker",
        "-q\ntouch marker",
        "-k `touch marker`",
        "-k $(touch marker)",
    ],
)
def test_run_tests_metachar_args_are_refused_without_side_effect(
    tmp_path: Path,
    args: str,
) -> None:
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    marker = tmp_path / "marker"
    with mock.patch("council_agent.tools.shell.subprocess.run") as run_mock:
        result = run_tests(path=str(tests_dir), args=args)
    assert not result.success
    assert result.metadata["rejection_reason"] == "shell_metachar"
    assert not marker.exists()
    run_mock.assert_not_called()


def test_run_tests_positional_outside_path_is_refused(tmp_path: Path) -> None:
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    outside = tmp_path.parent / f"{tmp_path.name}-outside-tests"
    outside.mkdir()
    try:
        with mock.patch("council_agent.tools.shell.subprocess.run") as run_mock:
            result = run_tests(path=str(tests_dir), args=str(outside))
        assert not result.success
        assert result.metadata["rejection_reason"] == "workspace_boundary"
        run_mock.assert_not_called()
    finally:
        outside.rmdir()


def test_run_tests_policy_precedes_confirmation_and_execution(
    tmp_path: Path,
) -> None:
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    policy = CouncilPolicy(denied_commands=["*pytest*"])
    with (
        active_policy(policy),
        mock.patch(
            "council_agent.tools.shell.require_confirmation"
        ) as confirm_mock,
        mock.patch("council_agent.tools.shell.subprocess.run") as run_mock,
    ):
        result = run_tests(path=str(tests_dir))
    assert not result.success
    assert result.metadata["policy_decision"] == "denied"
    confirm_mock.assert_not_called()
    run_mock.assert_not_called()


def test_run_tests_is_write_classified_and_confirmation_can_refuse(
    tmp_path: Path,
) -> None:
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    with (
        confirmation_policy(ConfirmMode.REFUSE),
        mock.patch("council_agent.tools.shell.subprocess.run") as run_mock,
    ):
        result = run_tests(path=str(tests_dir))
    assert not result.success
    assert result.metadata["classification"] == "write"
    assert result.metadata["matched_rule"] == "run-tests"
    assert result.metadata["confirmation"] == "refused"
    assert "exit_code" not in result.metadata
    run_mock.assert_not_called()
