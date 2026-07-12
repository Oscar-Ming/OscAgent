from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from oscagent.tools.base import ToolDefinition, ToolPermission, ToolResult


class GitStatusTool:
    def __init__(self, workspace_root: Path) -> None:
        self._workspace_root = workspace_root

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="git_status",
            description="Show the current Git branch and working tree status.",
            input_schema={"type": "object", "properties": {}},
            permission=ToolPermission.READ_ONLY,
        )

    def execute(self, arguments: dict[str, Any]) -> ToolResult:
        completed = subprocess.run(
            ["git", "status", "--short", "--branch"],
            cwd=self._workspace_root,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            shell=False,
        )

        content = completed.stdout.strip()
        if completed.returncode != 0:
            content = completed.stderr.strip() or "git status failed"

        return ToolResult(
            tool_name=self.definition.name,
            content=content or "(clean working tree)",
            metadata={"returncode": completed.returncode},
        )
