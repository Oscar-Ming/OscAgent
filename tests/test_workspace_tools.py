from __future__ import annotations

from pathlib import Path

import pytest

from oscagent.tools.workspace import (
    ListFilesTool,
    ReadFileTool,
    SearchTextTool,
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
