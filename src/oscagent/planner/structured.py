from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from oscagent.actions import PendingOperation
from oscagent.llm import ChatMessage, LLMProvider
from oscagent.tools import ToolDefinition, ToolRegistry
from oscagent.tools.workspace import IGNORED_DIRS, resolve_workspace_path


@dataclass(frozen=True)
class StructuredToolPlan:
    description: str
    operations: list[PendingOperation]


class StructuredToolPlanner:
    """Translate a workspace request into a bounded, validated tool plan."""

    _PATH_ARGUMENTS = {"path", "source", "destination"}

    def __init__(
        self,
        llm_provider: LLMProvider,
        model: str,
        registry: ToolRegistry,
        workspace_root: Path,
        *,
        max_operations: int = 20,
        max_workspace_entries: int = 200,
    ) -> None:
        self._llm_provider = llm_provider
        self._model = model
        self._registry = registry
        self._workspace_root = workspace_root
        self._max_operations = max_operations
        self._max_workspace_entries = max_workspace_entries

    async def plan(self, prompt: str, *, context: str | None = None) -> StructuredToolPlan:
        response = await self._llm_provider.chat(
            [
                ChatMessage(role="system", content=self._system_prompt(context)),
                ChatMessage(role="user", content=prompt),
            ],
            model=self._model,
        )
        payload = self._parse_json(response)
        return self._validate_payload(payload)

    def _system_prompt(self, context: str | None = None) -> str:
        tool_payload = [self._serialize_definition(item) for item in self._registry.definitions()]
        lines = [
            "You are the planning component of OscAgent.",
            "Convert the user's workspace request into a JSON tool plan.",
            "Return JSON only, with no markdown or explanation.",
            "Use only the registered tools and preserve the user's requested filenames.",
            "Every operation is reviewed and confirmed by the user before execution.",
            "Do not invent source files that are absent from the workspace listing.",
            f"The plan may contain at most {self._max_operations} operations.",
            'Schema: {"description": "short summary", "operations": '
            '[{"tool_name": "tool", "arguments": {}}]}',
            f"Registered tools: {json.dumps(tool_payload, ensure_ascii=False)}",
            "Current workspace entries:",
            self._workspace_listing(),
        ]
        tool_names = {item.name for item in self._registry.definitions()}
        if "git_commit" in tool_names:
            lines.extend(
                [
                    "Development workflow rules:",
                    "- Read-only development tools execute immediately and do not "
                    "need confirmation.",
                    "- Every git_commit plan must include run_tests and run_lint first.",
                    "- git_commit paths must be explicit changed paths, never '.' or '*'.",
                    "- Never include secrets, .env files, or unrelated untracked files.",
                    "- Never put git_commit and git_push in the same plan.",
                    "- Use git_push only when the user explicitly asks to push.",
                ]
            )
        if context:
            lines.extend(["Trusted runtime context:", context])
        return "\n".join(lines)

    def _workspace_listing(self) -> str:
        root = self._workspace_root.resolve()
        if not root.exists():
            return "(workspace does not exist)"

        entries: list[str] = []
        for path in sorted(root.rglob("*")):
            relative = path.relative_to(root)
            if any(part in IGNORED_DIRS for part in relative.parts):
                continue
            entries.append(relative.as_posix() + ("/" if path.is_dir() else ""))
            if len(entries) >= self._max_workspace_entries:
                entries.append("...[truncated]")
                break
        return "\n".join(entries) if entries else "(empty workspace)"

    def _serialize_definition(self, definition: ToolDefinition) -> dict[str, Any]:
        return {
            "name": definition.name,
            "description": definition.description,
            "input_schema": definition.input_schema,
            "permission": definition.permission.value,
        }

    def _parse_json(self, response: str) -> dict[str, Any]:
        cleaned = response.strip()
        fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", cleaned, flags=re.DOTALL)
        if fenced:
            cleaned = fenced.group(1)
        try:
            payload = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise ValueError("The model did not return a valid JSON plan.") from exc
        if not isinstance(payload, dict):
            raise ValueError("The model plan must be a JSON object.")
        return payload

    def _validate_payload(self, payload: dict[str, Any]) -> StructuredToolPlan:
        description = payload.get("description")
        raw_operations = payload.get("operations")
        if not isinstance(description, str) or not description.strip():
            raise ValueError("The model plan is missing a description.")
        if not isinstance(raw_operations, list) or not raw_operations:
            raise ValueError("The model plan contains no operations.")
        if len(raw_operations) > self._max_operations:
            raise ValueError(
                f"The model plan exceeds the {self._max_operations}-operation limit."
            )

        definitions = {item.name: item for item in self._registry.definitions()}
        operations: list[PendingOperation] = []
        for index, raw_operation in enumerate(raw_operations, start=1):
            if not isinstance(raw_operation, dict):
                raise ValueError(f"Operation {index} must be a JSON object.")
            tool_name = raw_operation.get("tool_name")
            arguments = raw_operation.get("arguments")
            if not isinstance(tool_name, str) or tool_name not in definitions:
                raise ValueError(f"Operation {index} uses an unregistered tool: {tool_name!r}.")
            if not isinstance(arguments, dict):
                raise ValueError(f"Operation {index} arguments must be a JSON object.")
            self._validate_arguments(index, definitions[tool_name], arguments)
            operations.append(PendingOperation(tool_name, arguments))

        return StructuredToolPlan(description.strip(), operations)

    def _validate_arguments(
        self,
        index: int,
        definition: ToolDefinition,
        arguments: dict[str, Any],
    ) -> None:
        schema = definition.input_schema
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        missing = [name for name in required if name not in arguments]
        if missing:
            raise ValueError(f"Operation {index} is missing arguments: {', '.join(missing)}.")

        unknown = sorted(set(arguments) - set(properties))
        if unknown:
            raise ValueError(f"Operation {index} has unknown arguments: {', '.join(unknown)}.")

        for name, value in arguments.items():
            expected_type = properties[name].get("type")
            if expected_type == "string" and not isinstance(value, str):
                raise ValueError(f"Operation {index} argument {name!r} must be a string.")
            if expected_type == "boolean" and not isinstance(value, bool):
                raise ValueError(f"Operation {index} argument {name!r} must be a boolean.")
            if expected_type == "integer" and (
                not isinstance(value, int) or isinstance(value, bool)
            ):
                raise ValueError(f"Operation {index} argument {name!r} must be an integer.")
            if expected_type == "array":
                if not isinstance(value, list):
                    raise ValueError(f"Operation {index} argument {name!r} must be an array.")
                item_type = properties[name].get("items", {}).get("type")
                if item_type == "string" and not all(isinstance(item, str) for item in value):
                    raise ValueError(
                        f"Operation {index} argument {name!r} must contain only strings."
                    )
            if name in self._PATH_ARGUMENTS:
                if not isinstance(value, str) or not value.strip():
                    raise ValueError(f"Operation {index} path {name!r} cannot be empty.")
                resolve_workspace_path(self._workspace_root, value)
