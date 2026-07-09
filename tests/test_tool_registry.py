from __future__ import annotations

import pytest

from oscagent.tools import ToolDefinition, ToolPermission, ToolRegistry, ToolResult


class ExampleTool:
    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="example",
            description="Example tool.",
            input_schema={},
            permission=ToolPermission.READ_ONLY,
        )

    def execute(self, arguments: dict[str, object]) -> ToolResult:
        return ToolResult(tool_name="example", content="ok")


def test_register_and_get_tool() -> None:
    registry = ToolRegistry()
    tool = ExampleTool()

    registry.register(tool)

    assert registry.get("example") is tool


def test_register_rejects_duplicate_tool() -> None:
    registry = ToolRegistry()
    registry.register(ExampleTool())

    with pytest.raises(ValueError, match="already registered"):
        registry.register(ExampleTool())


def test_get_rejects_unknown_tool() -> None:
    registry = ToolRegistry()

    with pytest.raises(KeyError, match="Unknown tool"):
        registry.get("missing")
