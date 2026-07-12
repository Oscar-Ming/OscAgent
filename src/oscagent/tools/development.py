from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from oscagent.tools.base import ToolDefinition, ToolPermission, ToolResult
from oscagent.tools.workspace import resolve_workspace_path

DEFAULT_TIMEOUT_SECONDS = 120
DEFAULT_MAX_OUTPUT_CHARS = 12_000
SENSITIVE_NAMES = {".env", ".env.local", ".env.production", "credentials.json"}


def _run_bounded(
    command: list[str],
    workspace_root: Path,
    *,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    max_output_chars: int = DEFAULT_MAX_OUTPUT_CHARS,
) -> ToolResult:
    try:
        completed = subprocess.run(
            command,
            cwd=workspace_root,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            shell=False,
        )
        output = "\n".join(
            part.strip()
            for part in (completed.stdout, completed.stderr)
            if part.strip()
        )
        truncated = len(output) > max_output_chars
        if truncated:
            output = output[:max_output_chars].rstrip() + "\n...[truncated]"
        return ToolResult(
            tool_name="",
            content=output or "(no output)",
            metadata={
                "returncode": completed.returncode,
                "command": command,
                "truncated": truncated,
            },
        )
    except subprocess.TimeoutExpired as exc:
        output = str(exc.stdout or exc.stderr or "").strip()
        return ToolResult(
            tool_name="",
            content=f"Command timed out after {timeout_seconds} seconds.\n{output}".strip(),
            metadata={"returncode": 124, "command": command, "timed_out": True},
        )


def _with_tool_name(result: ToolResult, tool_name: str) -> ToolResult:
    return ToolResult(tool_name=tool_name, content=result.content, metadata=result.metadata)


class RunTestsTool:
    def __init__(self, workspace_root: Path) -> None:
        self._workspace_root = workspace_root

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="run_tests",
            description="Run the project's complete pytest test suite.",
            input_schema={"type": "object", "properties": {}},
            permission=ToolPermission.READ_ONLY,
        )

    def execute(self, arguments: dict[str, Any]) -> ToolResult:
        result = _run_bounded([sys.executable, "-m", "pytest"], self._workspace_root)
        return _with_tool_name(result, self.definition.name)


class RunLintTool:
    def __init__(self, workspace_root: Path) -> None:
        self._workspace_root = workspace_root

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="run_lint",
            description="Run Ruff checks for the complete project.",
            input_schema={"type": "object", "properties": {}},
            permission=ToolPermission.READ_ONLY,
        )

    def execute(self, arguments: dict[str, Any]) -> ToolResult:
        result = _run_bounded(
            [sys.executable, "-m", "ruff", "check", "."],
            self._workspace_root,
        )
        return _with_tool_name(result, self.definition.name)


class GitDiffTool:
    def __init__(self, workspace_root: Path) -> None:
        self._workspace_root = workspace_root

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="git_diff",
            description="Show the current Git diff without changing the repository.",
            input_schema={
                "type": "object",
                "properties": {"staged": {"type": "boolean"}},
            },
            permission=ToolPermission.READ_ONLY,
        )

    def execute(self, arguments: dict[str, Any]) -> ToolResult:
        command = ["git", "diff"]
        if bool(arguments.get("staged", False)):
            command.append("--cached")
        result = _run_bounded(command, self._workspace_root, timeout_seconds=30)
        return _with_tool_name(result, self.definition.name)


class GitLogTool:
    def __init__(self, workspace_root: Path) -> None:
        self._workspace_root = workspace_root

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="git_log",
            description="Show recent Git commits without changing the repository.",
            input_schema={
                "type": "object",
                "properties": {
                    "max_count": {"type": "integer", "minimum": 1, "maximum": 20}
                },
            },
            permission=ToolPermission.READ_ONLY,
        )

    def execute(self, arguments: dict[str, Any]) -> ToolResult:
        max_count = max(1, min(int(arguments.get("max_count", 10)), 20))
        result = _run_bounded(
            ["git", "log", "--oneline", f"-{max_count}"],
            self._workspace_root,
            timeout_seconds=30,
        )
        return _with_tool_name(result, self.definition.name)


class GitCommitTool:
    def __init__(self, workspace_root: Path) -> None:
        self._workspace_root = workspace_root

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="git_commit",
            description="Stage explicit workspace paths and create a Git commit.",
            input_schema={
                "type": "object",
                "properties": {
                    "message": {"type": "string"},
                    "paths": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["message", "paths"],
            },
            permission=ToolPermission.GIT_WRITE,
        )

    def execute(self, arguments: dict[str, Any]) -> ToolResult:
        message = str(arguments["message"]).strip()
        paths = [str(path) for path in arguments["paths"]]
        self.validate(arguments)

        add_result = _run_bounded(
            ["git", "add", "--", *paths],
            self._workspace_root,
            timeout_seconds=30,
        )
        if add_result.metadata and add_result.metadata["returncode"] != 0:
            raise RuntimeError(f"git add failed: {add_result.content}")
        commit_result = _run_bounded(
            ["git", "commit", "-m", message],
            self._workspace_root,
            timeout_seconds=60,
        )
        return _with_tool_name(commit_result, self.definition.name)

    def validate(self, arguments: dict[str, Any]) -> None:
        message = str(arguments["message"]).strip()
        paths = [str(path) for path in arguments["paths"]]
        if not message or "\n" in message or len(message) > 200:
            raise ValueError("Commit message must be one non-empty line up to 200 characters.")
        if not paths:
            raise ValueError("Git commit requires at least one explicit path.")
        self._validate_paths(paths)

    def _validate_paths(self, paths: list[str]) -> None:
        for requested_path in paths:
            if requested_path in {".", "*"}:
                raise ValueError("Git commit requires explicit paths; broad staging is disabled.")
            resolved = resolve_workspace_path(self._workspace_root, requested_path)
            relative_parts = resolved.relative_to(self._workspace_root.resolve()).parts
            lowered_parts = {part.lower() for part in relative_parts}
            if lowered_parts & SENSITIVE_NAMES or any("secret" in part for part in lowered_parts):
                raise ValueError(f"Sensitive path cannot be committed: {requested_path}")


class GitPushTool:
    _SAFE_NAME = re.compile(r"^[A-Za-z0-9._/-]+$")

    def __init__(self, workspace_root: Path) -> None:
        self._workspace_root = workspace_root

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="git_push",
            description="Push the current local branch to a named Git remote without force.",
            input_schema={
                "type": "object",
                "properties": {
                    "remote": {"type": "string"},
                    "branch": {"type": "string"},
                },
                "required": ["remote", "branch"],
            },
            permission=ToolPermission.REMOTE_WRITE,
        )

    def execute(self, arguments: dict[str, Any]) -> ToolResult:
        remote = str(arguments["remote"]).strip()
        branch = str(arguments["branch"]).strip()
        self.validate(arguments)
        result = _run_bounded(
            ["git", "push", remote, branch],
            self._workspace_root,
            timeout_seconds=120,
        )
        return _with_tool_name(result, self.definition.name)

    def validate(self, arguments: dict[str, Any]) -> None:
        remote = str(arguments["remote"]).strip()
        branch = str(arguments["branch"]).strip()
        if not self._SAFE_NAME.fullmatch(remote) or "/" in remote or remote.startswith("-"):
            raise ValueError("Git remote must be a safe configured remote name.")
        if not self._SAFE_NAME.fullmatch(branch) or branch.startswith("-"):
            raise ValueError("Git branch name is invalid.")
