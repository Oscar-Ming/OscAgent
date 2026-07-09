from __future__ import annotations

from pathlib import Path
from typing import Any

from oscagent.tools.base import ToolDefinition, ToolPermission, ToolResult

IGNORED_DIRS = {
    ".git",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
    ".venv",
    "data",
    "logs",
    "venv",
}


def resolve_workspace_path(workspace_root: Path, requested_path: str) -> Path:
    root = workspace_root.resolve()
    candidate = (root / requested_path).resolve()

    if candidate != root and root not in candidate.parents:
        raise ValueError("Path is outside the workspace.")

    return candidate


class ListFilesTool:
    def __init__(self, workspace_root: Path) -> None:
        self._workspace_root = workspace_root

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="list_files",
            description="List files and directories under a workspace path.",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "max_depth": {"type": "integer", "minimum": 1, "maximum": 5},
                },
            },
            permission=ToolPermission.READ_ONLY,
        )

    def execute(self, arguments: dict[str, Any]) -> ToolResult:
        requested_path = str(arguments.get("path", "."))
        max_depth = int(arguments.get("max_depth", 3))
        max_depth = max(1, min(max_depth, 5))
        root = resolve_workspace_path(self._workspace_root, requested_path)

        if not root.exists():
            raise FileNotFoundError(f"Path does not exist: {requested_path}")
        if not root.is_dir():
            raise ValueError(f"Path is not a directory: {requested_path}")

        lines: list[str] = []
        base_depth = len(root.parts)
        for path in sorted(root.rglob("*")):
            if any(part in IGNORED_DIRS for part in path.relative_to(root).parts):
                continue
            depth = len(path.parts) - base_depth
            if depth > max_depth:
                continue
            indent = "  " * (depth - 1)
            suffix = "/" if path.is_dir() else ""
            lines.append(f"{indent}{path.name}{suffix}")

        return ToolResult(
            tool_name=self.definition.name,
            content="\n".join(lines) if lines else "(empty directory)",
            metadata={"path": requested_path, "max_depth": max_depth},
        )


class ReadFileTool:
    def __init__(self, workspace_root: Path, max_chars: int = 8000) -> None:
        self._workspace_root = workspace_root
        self._max_chars = max_chars

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="read_file",
            description="Read a UTF-8 text file from the workspace.",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "max_chars": {"type": "integer", "minimum": 1},
                },
                "required": ["path"],
            },
            permission=ToolPermission.READ_ONLY,
        )

    def execute(self, arguments: dict[str, Any]) -> ToolResult:
        requested_path = str(arguments["path"])
        max_chars = int(arguments.get("max_chars", self._max_chars))
        max_chars = max(1, min(max_chars, self._max_chars))
        path = resolve_workspace_path(self._workspace_root, requested_path)

        if not path.exists():
            raise FileNotFoundError(f"File does not exist: {requested_path}")
        if not path.is_file():
            raise ValueError(f"Path is not a file: {requested_path}")

        content = path.read_text(encoding="utf-8", errors="replace")
        truncated = len(content) > max_chars
        if truncated:
            content = content[:max_chars] + "\n...[truncated]"

        return ToolResult(
            tool_name=self.definition.name,
            content=content,
            metadata={"path": requested_path, "truncated": truncated},
        )


class SearchTextTool:
    def __init__(self, workspace_root: Path, max_results: int = 30) -> None:
        self._workspace_root = workspace_root
        self._max_results = max_results

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="search_text",
            description="Search text files under the workspace for a literal query.",
            input_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "path": {"type": "string"},
                    "max_results": {"type": "integer", "minimum": 1},
                },
                "required": ["query"],
            },
            permission=ToolPermission.READ_ONLY,
        )

    def execute(self, arguments: dict[str, Any]) -> ToolResult:
        query = str(arguments["query"])
        requested_path = str(arguments.get("path", "."))
        max_results = int(arguments.get("max_results", self._max_results))
        max_results = max(1, min(max_results, self._max_results))
        root = resolve_workspace_path(self._workspace_root, requested_path)

        if not root.exists():
            raise FileNotFoundError(f"Path does not exist: {requested_path}")

        files = [root] if root.is_file() else sorted(root.rglob("*"))
        matches: list[str] = []
        for path in files:
            if len(matches) >= max_results:
                break
            ignored_path = any(part in IGNORED_DIRS for part in path.relative_to(root).parts)
            if not path.is_file() or ignored_path:
                continue

            try:
                lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                continue

            for line_number, line in enumerate(lines, start=1):
                if query.lower() in line.lower():
                    relative_path = path.relative_to(self._workspace_root)
                    matches.append(f"{relative_path}:{line_number}: {line.strip()}")
                    if len(matches) >= max_results:
                        break

        return ToolResult(
            tool_name=self.definition.name,
            content="\n".join(matches) if matches else "(no matches)",
            metadata={"query": query, "path": requested_path, "max_results": max_results},
        )
