"""Tests for filesystem tools."""

from pathlib import Path

from council_agent.tools.filesystem import delete_file, list_dir, read_file, write_file


def test_write_and_read_file(tmp_path: Path) -> None:
    target = tmp_path / "hello.txt"
    write_result = write_file(str(target), "hi")
    assert write_result.success
    assert write_result.metadata["created"] is True
    assert write_result.metadata["bytes_written"] == 2

    read_result = read_file(str(target))
    assert read_result.success
    assert read_result.output == "hi"
    assert read_result.metadata["size"] == 2
    assert read_result.metadata["encoding"] == "utf-8"


def test_write_file_creates_parent_dirs(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "dir" / "file.txt"
    result = write_file(str(target), "content")
    assert result.success
    assert target.read_text(encoding="utf-8") == "content"
    assert result.metadata["created"] is True


def test_write_file_overwrite(tmp_path: Path) -> None:
    target = tmp_path / "existing.txt"
    target.write_text("old", encoding="utf-8")
    result = write_file(str(target), "new")
    assert result.success
    assert result.metadata["created"] is False
    assert target.read_text(encoding="utf-8") == "new"


def test_read_file_not_found(tmp_path: Path) -> None:
    result = read_file(str(tmp_path / "missing.txt"))
    assert not result.success
    assert result.error is not None
    assert "not found" in result.error.lower()


def test_read_file_is_directory(tmp_path: Path) -> None:
    result = read_file(str(tmp_path))
    assert not result.success
    assert result.error is not None
    assert "directory" in result.error.lower()


def test_list_dir(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("a", encoding="utf-8")
    (tmp_path / "b.txt").write_text("b", encoding="utf-8")
    (tmp_path / "subdir").mkdir()

    result = list_dir(str(tmp_path))
    assert result.success
    assert result.metadata["entries"] == ["a.txt", "b.txt", "subdir"]
    assert result.output == "a.txt\nb.txt\nsubdir"


def test_list_dir_empty(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    result = list_dir(str(empty))
    assert result.success
    assert result.metadata["entries"] == []
    assert result.output == ""


def test_list_dir_not_directory(tmp_path: Path) -> None:
    file_path = tmp_path / "file.txt"
    file_path.write_text("x", encoding="utf-8")
    result = list_dir(str(file_path))
    assert not result.success
    assert result.error is not None


def test_delete_file(tmp_path: Path) -> None:
    target = tmp_path / "remove-me.txt"
    target.write_text("bye", encoding="utf-8")
    result = delete_file(str(target))
    assert result.success
    assert result.metadata["deleted"] is True
    assert not target.exists()


def test_delete_file_not_found(tmp_path: Path) -> None:
    result = delete_file(str(tmp_path / "missing.txt"))
    assert not result.success
    assert result.error is not None


def test_delete_file_directory_fails(tmp_path: Path) -> None:
    subdir = tmp_path / "subdir"
    subdir.mkdir()
    result = delete_file(str(subdir))
    assert not result.success
    assert result.error is not None
    assert "directory" in result.error.lower()
