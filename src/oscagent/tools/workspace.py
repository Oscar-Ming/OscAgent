from __future__ import annotations

import shutil
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


class CreateDirectoryTool:
    def __init__(self, workspace_root: Path) -> None:
        self._workspace_root = workspace_root

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="create_directory",
            description="Create a directory inside the workspace.",
            input_schema={
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
            permission=ToolPermission.WORKSPACE_WRITE,
        )

    def execute(self, arguments: dict[str, Any]) -> ToolResult:
        requested_path = str(arguments["path"])
        path = resolve_workspace_path(self._workspace_root, requested_path)
        path.mkdir(parents=True, exist_ok=True)
        return ToolResult(
            tool_name=self.definition.name,
            content=f"Created directory: {requested_path}",
            metadata={"path": requested_path},
        )


class WriteFileTool:
    def __init__(self, workspace_root: Path) -> None:
        self._workspace_root = workspace_root

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="write_file",
            description="Write a UTF-8 text file inside the workspace.",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                    "overwrite": {"type": "boolean"},
                },
                "required": ["path", "content"],
            },
            permission=ToolPermission.WORKSPACE_WRITE,
        )

    def execute(self, arguments: dict[str, Any]) -> ToolResult:
        requested_path = str(arguments["path"])
        content = str(arguments["content"])
        overwrite = bool(arguments.get("overwrite", False))
        path = resolve_workspace_path(self._workspace_root, requested_path)

        if path.exists() and not overwrite:
            raise FileExistsError(f"File already exists: {requested_path}")

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return ToolResult(
            tool_name=self.definition.name,
            content=f"Wrote file: {requested_path}",
            metadata={"path": requested_path, "overwrite": overwrite},
        )


class CopyFileTool:
    def __init__(self, workspace_root: Path) -> None:
        self._workspace_root = workspace_root

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="copy_file",
            description="Copy a file inside the workspace.",
            input_schema={
                "type": "object",
                "properties": {
                    "source": {"type": "string"},
                    "destination": {"type": "string"},
                    "overwrite": {"type": "boolean"},
                },
                "required": ["source", "destination"],
            },
            permission=ToolPermission.WORKSPACE_WRITE,
        )

    def execute(self, arguments: dict[str, Any]) -> ToolResult:
        source = str(arguments["source"])
        destination = str(arguments["destination"])
        overwrite = bool(arguments.get("overwrite", False))
        source_path = resolve_workspace_path(self._workspace_root, source)
        destination_path = resolve_workspace_path(self._workspace_root, destination)

        if not source_path.is_file():
            raise FileNotFoundError(f"Source file does not exist: {source}")
        if destination_path.exists() and not overwrite:
            raise FileExistsError(f"Destination already exists: {destination}")

        destination_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, destination_path)
        return ToolResult(
            tool_name=self.definition.name,
            content=f"Copied {source} -> {destination}",
            metadata={"source": source, "destination": destination, "overwrite": overwrite},
        )


class MoveFileTool:
    def __init__(self, workspace_root: Path) -> None:
        self._workspace_root = workspace_root

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="move_file",
            description="Move a file inside the workspace.",
            input_schema={
                "type": "object",
                "properties": {
                    "source": {"type": "string"},
                    "destination": {"type": "string"},
                    "overwrite": {"type": "boolean"},
                },
                "required": ["source", "destination"],
            },
            permission=ToolPermission.FILE_MOVE,
        )

    def execute(self, arguments: dict[str, Any]) -> ToolResult:
        source = str(arguments["source"])
        destination = str(arguments["destination"])
        overwrite = bool(arguments.get("overwrite", False))
        source_path = resolve_workspace_path(self._workspace_root, source)
        destination_path = resolve_workspace_path(self._workspace_root, destination)

        if not source_path.is_file():
            raise FileNotFoundError(f"Source file does not exist: {source}")
        if destination_path.exists() and not overwrite:
            raise FileExistsError(f"Destination already exists: {destination}")

        destination_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source_path), str(destination_path))
        return ToolResult(
            tool_name=self.definition.name,
            content=f"Moved {source} -> {destination}",
            metadata={"source": source, "destination": destination, "overwrite": overwrite},
        )
