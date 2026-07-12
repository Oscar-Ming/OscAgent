from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol


class ToolPermission(StrEnum):
    READ_ONLY = "read_only"
    WORKSPACE_WRITE = "workspace_write"
    FILE_MOVE = "file_move"
    GIT_WRITE = "git_write"
    REMOTE_WRITE = "remote_write"


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    input_schema: dict[str, Any]
    permission: ToolPermission


@dataclass(frozen=True)
class ToolResult:
    tool_name: str
    content: str
    metadata: dict[str, Any] | None = None


class Tool(Protocol):
    @property
    def definition(self) -> ToolDefinition:
        """Return the public tool definition."""

    def execute(self, arguments: dict[str, Any]) -> ToolResult:
        """Execute the tool and return a text observation."""
