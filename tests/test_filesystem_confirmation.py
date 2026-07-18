"""Filesystem mutate tools + confirmation gate."""

from __future__ import annotations

from pathlib import Path

from council_agent.security import ConfirmMode, confirmation_policy
from council_agent.tools.filesystem import delete_file, read_file, write_file


def test_write_file_denied_in_refuse_mode(tmp_path: Path) -> None:
    target = tmp_path / "new.txt"

    with confirmation_policy(ConfirmMode.REFUSE):
        result = write_file("new.txt", "hello")

    assert result.success is False
    assert result.metadata.get("confirmation") == "refused"
    assert not target.exists()


def test_delete_file_denied_leaves_file(tmp_path: Path) -> None:
    target = tmp_path / "keep.txt"
    target.write_text("x", encoding="utf-8")

    with confirmation_policy(ConfirmMode.REFUSE):
        result = delete_file("keep.txt")

    assert result.success is False
    assert result.metadata.get("confirmation") == "refused"
    assert target.exists()


def test_write_file_auto_allows(tmp_path: Path) -> None:
    with confirmation_policy(ConfirmMode.AUTO):
        result = write_file("ok.txt", "data")

    assert result.success is True
    assert result.metadata.get("confirmation") == "auto"
    assert (tmp_path / "ok.txt").read_text(encoding="utf-8") == "data"


def test_read_file_not_gated_in_refuse_mode(tmp_path: Path) -> None:
    (tmp_path / "r.txt").write_text("hi", encoding="utf-8")

    with confirmation_policy(ConfirmMode.REFUSE):
        result = read_file("r.txt")

    assert result.success is True
    assert result.output == "hi"
    assert "confirmation" not in result.metadata


def test_compat_allows_write_without_confirmation_meta(tmp_path: Path) -> None:
    result = write_file("c.txt", "compat")
    assert result.success is True
    assert (tmp_path / "c.txt").read_text(encoding="utf-8") == "compat"
    assert "confirmation" not in result.metadata
