"""Public tool boundary tests for the policy dispatcher."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest import mock

import pytest

import council_agent.tools as product_tools
from council_agent.security.middleware import (
    SecurityContext,
    SecurityContextError,
    get_security_context,
    invoke,
    without_security_context,
)
from council_agent.tools import (
    delete_file,
    read_file,
    run_command,
    run_tests,
    write_file,
)
from council_agent.tools.filesystem import _write_file


def test_public_write_without_context_has_no_side_effect(tmp_path: Path) -> None:
    target = tmp_path / "blocked.txt"

    with without_security_context():
        result = write_file(str(target), "blocked")

    assert result.success is False
    assert result.metadata["rejection_reason"] == "security_context_missing"
    assert not target.exists()


def test_public_shell_without_context_starts_no_process() -> None:
    with (
        without_security_context(),
        mock.patch("council_agent.tools.shell.subprocess.run") as run_mock,
    ):
        result = run_command("echo blocked")

    assert result.success is False
    assert result.metadata["rejection_reason"] == "security_context_missing"
    run_mock.assert_not_called()


def test_direct_public_api_is_tracked_and_correlated(tmp_path: Path) -> None:
    context = get_security_context()
    assert context is not None
    before = len(context.tracker.summaries)
    target = tmp_path / "tracked.txt"

    result = write_file(str(target), "tracked")

    assert result.success is True
    assert target.read_text(encoding="utf-8") == "tracked"
    assert len(context.tracker.summaries) == before + 1
    summary = context.tracker.summaries[-1]
    assert summary.tool == "write_file"
    assert summary.metadata["action_id"] == result.metadata["action_id"]
    assert summary.metadata["request_id"] == context.request_id
    assert summary.metadata["decision"] == "allow"


def test_public_filesystem_tools_cannot_access_project_policy(
    tmp_path: Path,
) -> None:
    target = tmp_path / "council.policy.yaml"
    original = 'schema_version: 1\ndenied_commands:\n  - "curl *"\n'
    target.write_text(original, encoding="utf-8")

    results = [
        read_file("council.policy.yaml"),
        write_file("council.policy.yaml", "schema_version: 1\n"),
        delete_file("council.policy.yaml"),
    ]

    assert all(result.success is False for result in results)
    assert all(
        result.metadata["rejection_reason"] == "denied_path"
        for result in results
    )
    assert all(result.metadata["decision"] == "deny" for result in results)
    assert target.read_text(encoding="utf-8") == original


def test_public_write_cannot_change_nested_project_policy(
    tmp_path: Path,
) -> None:
    nested = tmp_path / "nested"
    nested.mkdir()
    target = nested / "council.policy.yaml"
    original = "schema_version: 1\n"
    target.write_text(original, encoding="utf-8")

    result = write_file(
        "nested/council.policy.yaml",
        "schema_version: 2\n",
    )

    assert result.success is False
    assert result.metadata["rejection_reason"] == "denied_path"
    assert result.metadata["decision"] == "deny"
    assert target.read_text(encoding="utf-8") == original


def test_supported_shell_cannot_delete_project_policy(
    tmp_path: Path,
) -> None:
    target = tmp_path / "council.policy.yaml"
    original = "schema_version: 1\n"
    target.write_text(original, encoding="utf-8")

    with mock.patch("council_agent.tools.shell.subprocess.run") as run_mock:
        result = run_command("rm council.policy.yaml")

    assert result.success is False
    assert result.metadata["rejection_reason"] == "denied_path"
    assert result.metadata["decision"] == "deny"
    assert target.read_text(encoding="utf-8") == original
    run_mock.assert_not_called()


def test_public_package_exports_only_dispatcher_backed_functions() -> None:
    assert {
        "read_file",
        "write_file",
        "list_dir",
        "delete_file",
        "run_command",
        "run_tests",
    }.issubset(set(product_tools.__all__))
    assert not any(name.startswith("_") for name in product_tools.__all__)


def test_private_mutation_helper_requires_active_context(tmp_path: Path) -> None:
    context = SecurityContext.create(tmp_path)
    target = tmp_path / "private-bypass.txt"

    with pytest.raises(SecurityContextError, match="not active"):
        _write_file(context, path=str(target), content="blocked")

    assert not target.exists()


def test_public_and_dispatcher_paths_return_same_denial() -> None:
    direct = run_command("unknown-product-command")
    dispatched = invoke("run_command", command="unknown-product-command")

    assert direct.success is dispatched.success is False
    assert (
        direct.metadata["rejection_reason"]
        == dispatched.metadata["rejection_reason"]
        == "unsupported"
    )
    assert direct.metadata["decision"] == dispatched.metadata["decision"] == "deny"


def test_run_tests_is_one_top_level_action(tmp_path: Path) -> None:
    context = get_security_context()
    assert context is not None
    before = len(context.tracker.summaries)
    completed = subprocess.CompletedProcess(
        args=[],
        returncode=0,
        stdout="1 passed in 0.01s\n",
        stderr="",
    )

    with mock.patch(
        "council_agent.tools.shell.subprocess.run",
        return_value=completed,
    ):
        result = run_tests(path=str(tmp_path))

    assert result.success is True
    assert len(context.tracker.summaries) == before + 1
    summary = context.tracker.summaries[-1]
    assert summary.tool == "run_tests"
    assert summary.metadata["action_id"] == result.metadata["action_id"]
    assert not any(
        item.tool == "run_command"
        for item in context.tracker.summaries[before:]
    )


def test_no_sandbox_context_creates_no_durable_evidence(tmp_path: Path) -> None:
    context = get_security_context()
    assert context is not None
    assert context.session is None
    assert context.audit_logger is None
    target = tmp_path / "read.txt"
    target.write_text("ok", encoding="utf-8")

    result = read_file(str(target))

    assert result.success is True
    assert result.metadata["request_id"] == context.request_id
    assert not (tmp_path / ".council").exists()
