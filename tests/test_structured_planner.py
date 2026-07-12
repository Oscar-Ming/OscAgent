from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from oscagent.llm import ChatMessage
from oscagent.planner import StructuredToolPlanner
from oscagent.tools import CreateDirectoryTool, MoveFileTool, ToolRegistry


class StaticProvider:
    def __init__(self, response: object) -> None:
        self.response = response
        self.messages: list[ChatMessage] = []

    async def chat(self, messages: list[ChatMessage], *, model: str) -> str:
        self.messages = messages
        return self.response if isinstance(self.response, str) else json.dumps(self.response)


def build_planner(tmp_path: Path, response: object, *, max_operations: int = 20):
    registry = ToolRegistry()
    registry.register(CreateDirectoryTool(tmp_path))
    registry.register(MoveFileTool(tmp_path))
    provider = StaticProvider(response)
    planner = StructuredToolPlanner(
        provider,
        "deepseek:deepseek-chat",
        registry,
        tmp_path,
        max_operations=max_operations,
    )
    return planner, provider


def test_planner_builds_multi_tool_plan_from_registered_tools(tmp_path: Path) -> None:
    (tmp_path / "scratch").mkdir()
    (tmp_path / "scratch" / "test.txt").write_text("one", encoding="utf-8")
    (tmp_path / "scratch" / "test2.txt").write_text("two", encoding="utf-8")
    response = {
        "description": "Move test files into gooner",
        "operations": [
            {"tool_name": "create_directory", "arguments": {"path": "gooner"}},
            {
                "tool_name": "move_file",
                "arguments": {
                    "source": "scratch/test.txt",
                    "destination": "gooner/test.txt",
                },
            },
            {
                "tool_name": "move_file",
                "arguments": {
                    "source": "scratch/test2.txt",
                    "destination": "gooner/test2.txt",
                },
            },
        ],
    }
    planner, provider = build_planner(tmp_path, response)

    plan = asyncio.run(planner.plan("把scratch里的test和test2文件整理到gooner文件夹"))

    assert len(plan.operations) == 3
    assert plan.operations[1].tool_name == "move_file"
    assert "scratch/test.txt" in provider.messages[0].content
    assert "move_file" in provider.messages[0].content


def test_planner_rejects_unregistered_tools(tmp_path: Path) -> None:
    planner, _ = build_planner(
        tmp_path,
        {
            "description": "Delete a file",
            "operations": [{"tool_name": "delete_file", "arguments": {"path": "a.txt"}}],
        },
    )

    with pytest.raises(ValueError, match="unregistered tool"):
        asyncio.run(planner.plan("delete a.txt"))


def test_planner_rejects_paths_outside_workspace(tmp_path: Path) -> None:
    planner, _ = build_planner(
        tmp_path,
        {
            "description": "Move outside",
            "operations": [
                {
                    "tool_name": "move_file",
                    "arguments": {"source": "a.txt", "destination": "../a.txt"},
                }
            ],
        },
    )

    with pytest.raises(ValueError, match="outside the workspace"):
        asyncio.run(planner.plan("move a.txt outside"))


def test_planner_enforces_operation_limit(tmp_path: Path) -> None:
    planner, _ = build_planner(
        tmp_path,
        {
            "description": "Too many operations",
            "operations": [
                {"tool_name": "create_directory", "arguments": {"path": f"dir-{index}"}}
                for index in range(3)
            ],
        },
        max_operations=2,
    )

    with pytest.raises(ValueError, match="2-operation limit"):
        asyncio.run(planner.plan("create three folders"))
