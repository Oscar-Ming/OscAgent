from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from oscagent.actions import PendingOperation
from oscagent.agent.trace import Trace
from oscagent.config import Settings
from oscagent.llm import LLMProvider
from oscagent.planner import StructuredToolPlanner
from oscagent.tools import (
    GitCommitTool,
    GitDiffTool,
    GitLogTool,
    GitPushTool,
    GitStatusTool,
    RunLintTool,
    RunTestsTool,
    ToolPermission,
    ToolRegistry,
    ToolResult,
)


@dataclass(frozen=True)
class DevelopmentWorkflowResult:
    description: str
    trace: Trace
    observations: list[ToolResult]
    pending_operations: list[PendingOperation]
    blocked_reason: str | None = None


class DevelopmentWorkflowAgent:
    def __init__(
        self,
        llm_provider: LLMProvider,
        settings: Settings,
        workspace_root: Path,
    ) -> None:
        self._workspace_root = workspace_root
        self._registry = build_development_tools(workspace_root)
        self._planner = StructuredToolPlanner(
            llm_provider,
            settings.model,
            self._registry,
            workspace_root,
        )

    async def run(self, prompt: str) -> DevelopmentWorkflowResult:
        preflight = self._registry.get("git_status").execute({})
        plan = await self._planner.plan(
            prompt,
            context=f"Current git status:\n{preflight.content}",
        )
        read_operations: list[PendingOperation] = []
        write_operations: list[PendingOperation] = []
        for operation in plan.operations:
            permission = self._registry.get(operation.tool_name).definition.permission
            if permission == ToolPermission.READ_ONLY:
                read_operations.append(operation)
            else:
                write_operations.append(operation)

        self._validate_write_plan(write_operations)
        self._validate_required_checks(plan.operations, write_operations)
        for operation in write_operations:
            tool = self._registry.get(operation.tool_name)
            if isinstance(tool, (GitCommitTool, GitPushTool)):
                tool.validate(operation.arguments)
        trace = Trace()
        observations: list[ToolResult] = []
        for operation in read_operations:
            tool = self._registry.get(operation.tool_name)
            try:
                result = tool.execute(operation.arguments)
            except Exception as exc:  # noqa: BLE001 - tool failures are user-visible.
                result = ToolResult(
                    tool_name=operation.tool_name,
                    content=f"Tool failed: {exc}",
                    metadata={"returncode": 1},
                )
            trace.add_step(operation.tool_name, operation.arguments, result.content)
            observations.append(result)
            if self._failed(result):
                return DevelopmentWorkflowResult(
                    plan.description,
                    trace,
                    observations,
                    [],
                    f"{operation.tool_name} failed; write operations were blocked.",
                )

        return DevelopmentWorkflowResult(
            plan.description,
            trace,
            observations,
            write_operations,
        )

    def _validate_write_plan(self, operations: list[PendingOperation]) -> None:
        if len(operations) > 1:
            raise ValueError("A development plan may contain only one Git write operation.")
        names = {operation.tool_name for operation in operations}
        if "git_commit" in names and "git_push" in names:
            raise ValueError("Commit and push require separate confirmation requests.")

    def _validate_required_checks(
        self,
        operations: list[PendingOperation],
        write_operations: list[PendingOperation],
    ) -> None:
        if not any(operation.tool_name == "git_commit" for operation in write_operations):
            return
        names = {operation.tool_name for operation in operations}
        if "run_tests" not in names:
            raise ValueError("Every commit plan must run tests first.")
        if "run_lint" not in names:
            raise ValueError("Every commit plan must run lint checks first.")

    def _failed(self, result: ToolResult) -> bool:
        return bool(result.metadata and int(result.metadata.get("returncode", 0)) != 0)


def build_development_tools(workspace_root: Path) -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(RunTestsTool(workspace_root))
    registry.register(RunLintTool(workspace_root))
    registry.register(GitStatusTool(workspace_root))
    registry.register(GitDiffTool(workspace_root))
    registry.register(GitLogTool(workspace_root))
    registry.register(GitCommitTool(workspace_root))
    registry.register(GitPushTool(workspace_root))
    return registry
