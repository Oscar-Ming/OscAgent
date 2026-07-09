from __future__ import annotations

from pathlib import Path

from oscagent.agent.trace import Trace
from oscagent.config import Settings
from oscagent.llm import ChatMessage, LLMProvider
from oscagent.tools.base import ToolResult
from oscagent.tools.git import GitStatusTool
from oscagent.tools.registry import ToolRegistry
from oscagent.tools.workspace import ListFilesTool, ReadFileTool

REPO_ANALYSIS_KEYWORDS = (
    "analyze repo",
    "analyze repository",
    "analyse repo",
    "repo analysis",
    "repository analysis",
    "project structure",
    "codebase structure",
    "分析项目",
    "项目结构",
    "分析一下当前",
)


def is_repo_analysis_request(prompt: str) -> bool:
    normalized = prompt.strip().lower()
    return any(keyword in normalized for keyword in REPO_ANALYSIS_KEYWORDS)


class RepoAnalysisAgent:
    def __init__(
        self,
        llm_provider: LLMProvider,
        settings: Settings | None = None,
        workspace_root: Path | None = None,
    ) -> None:
        self._llm_provider = llm_provider
        self._settings = settings or Settings()
        self._workspace_root = workspace_root or Path.cwd()
        self._registry = ToolRegistry()
        self._registry.register(ListFilesTool(self._workspace_root))
        self._registry.register(ReadFileTool(self._workspace_root))
        self._registry.register(GitStatusTool(self._workspace_root))

    async def analyze(self, prompt: str) -> tuple[str, Trace]:
        trace = Trace()
        observations: list[ToolResult] = []

        for tool_name, arguments in self._planned_tool_calls():
            tool = self._registry.get(tool_name)
            try:
                result = tool.execute(arguments)
            except Exception as exc:  # noqa: BLE001 - tool errors should be visible in traces.
                result = ToolResult(tool_name=tool_name, content=f"Tool failed: {exc}")

            trace.add_step(tool_name, arguments, result.content)
            observations.append(result)

        answer = await self._summarize(prompt, observations, trace)
        return answer, trace

    def _planned_tool_calls(self) -> list[tuple[str, dict[str, object]]]:
        calls: list[tuple[str, dict[str, object]]] = [
            ("list_files", {"path": ".", "max_depth": 3}),
            ("git_status", {}),
        ]

        for path in ("README.md", "ROADMAP.md", "pyproject.toml"):
            if (self._workspace_root / path).exists():
                calls.append(("read_file", {"path": path, "max_chars": 6000}))

        return calls

    async def _summarize(
        self,
        prompt: str,
        observations: list[ToolResult],
        trace: Trace,
    ) -> str:
        context_blocks = []
        for result in observations:
            context_blocks.append(
                "\n".join(
                    [
                        f"## Tool: {result.tool_name}",
                        result.content,
                    ]
                )
            )

        messages = [
            ChatMessage(
                role="system",
                content=(
                    "You are OscAgent, a repository analysis agent. Use only the supplied "
                    "tool observations. Summarize the project structure, current capabilities, "
                    "Git state, and practical next steps. Be concise and concrete."
                ),
            ),
            ChatMessage(
                role="user",
                content="\n\n".join(
                    [
                        f"User request: {prompt}",
                        "Tool trace:",
                        trace.to_markdown(),
                        "Observations:",
                        "\n\n".join(context_blocks),
                    ]
                ),
            ),
        ]
        return await self._llm_provider.chat(messages, model=self._settings.model)
