from __future__ import annotations

from pathlib import Path

import pytest

from oscagent.tools.workspace import (
    CopyFileTool,
    CreateDirectoryTool,
    ListFilesTool,
    MoveFileTool,
    ReadFileTool,
    SearchTextTool,
    WriteFileTool,
    resolve_workspace_path,
)


def test_resolve_workspace_path_rejects_escape(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="outside"):
        resolve_workspace_path(tmp_path, "../outside.txt")


def test_list_files_tool_lists_workspace_files(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("print('hello')", encoding="utf-8")

    result = ListFilesTool(tmp_path).execute({"path": ".", "max_depth": 2})

    assert "src/" in result.content
    assert "app.py" in result.content


def test_read_file_tool_reads_text(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# Hello", encoding="utf-8")

    result = ReadFileTool(tmp_path).execute({"path": "README.md"})

    assert result.content == "# Hello"


def test_search_text_tool_finds_literal_matches(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("OscAgent\nAgent runtime", encoding="utf-8")

    result = SearchTextTool(tmp_path).execute({"query": "runtime"})

    assert "README.md:2" in result.content
    assert "Agent runtime" in result.content


def test_create_directory_tool_creates_directory(tmp_path: Path) -> None:
    result = CreateDirectoryTool(tmp_path).execute({"path": "docs"})

    assert (tmp_path / "docs").is_dir()
    assert "Created directory" in result.content


def test_write_file_tool_writes_text(tmp_path: Path) -> None:
    result = WriteFileTool(tmp_path).execute({"path": "docs/summary.md", "content": "hello"})

    assert (tmp_path / "docs" / "summary.md").read_text(encoding="utf-8") == "hello"
    assert "Wrote file" in result.content


def test_write_file_tool_rejects_overwrite_by_default(tmp_path: Path) -> None:
    (tmp_path / "notes.txt").write_text("old", encoding="utf-8")

    with pytest.raises(FileExistsError):
        WriteFileTool(tmp_path).execute({"path": "notes.txt", "content": "new"})


def test_copy_file_tool_copies_file(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# Hello", encoding="utf-8")

    result = CopyFileTool(tmp_path).execute(
        {"source": "README.md", "destination": "docs/README.md"}
    )

    assert (tmp_path / "docs" / "README.md").read_text(encoding="utf-8") == "# Hello"
    assert "Copied" in result.content


def test_move_file_tool_moves_file(tmp_path: Path) -> None:
    (tmp_path / "draft.txt").write_text("draft", encoding="utf-8")

    result = MoveFileTool(tmp_path).execute(
        {"source": "draft.txt", "destination": "archive/draft.txt"}
    )

    assert not (tmp_path / "draft.txt").exists()
    assert (tmp_path / "archive" / "draft.txt").read_text(encoding="utf-8") == "draft"
    assert "Moved" in result.content


def test_write_file_tool_rejects_workspace_escape(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="outside"):
        WriteFileTool(tmp_path).execute({"path": "../escape.txt", "content": "nope"})
