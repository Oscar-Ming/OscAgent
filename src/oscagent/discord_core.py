from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from oscagent.actions import PendingAction, PendingActionStore, PendingOperation
from oscagent.agent import RepoAnalysisAgent, is_repo_analysis_request
from oscagent.config import Settings
from oscagent.llm import ChatMessage, LLMProvider
from oscagent.memory import MemoryRecord, MemoryStore
from oscagent.tools import (
    CopyFileTool,
    CreateDirectoryTool,
    MoveFileTool,
    ToolRegistry,
    WriteFileTool,
)


@dataclass(frozen=True)
class DiscordResponse:
    content: str


class DiscordCommandHandler:
    def __init__(
        self,
        llm_provider: LLMProvider,
        settings: Settings | None = None,
        memory_store: MemoryStore | None = None,
        action_store: PendingActionStore | None = None,
        workspace_root: Path | None = None,
    ) -> None:
        self._llm_provider = llm_provider
        self._settings = settings or Settings()
        self._memory_store = memory_store or MemoryStore(self._settings.db_path)
        self._action_store = action_store or PendingActionStore(self._settings.db_path)
        self._workspace_root = workspace_root or Path.cwd()
        self._write_tools = self._build_write_tools()
        self._clear_all_pending = False

    async def handle_ask(self, prompt: str) -> DiscordResponse:
        cleaned_prompt = prompt.strip()
        if not cleaned_prompt:
            return DiscordResponse("Please include a question after `/ask`.")

        if self._is_clear_all_confirmation(cleaned_prompt):
            if not self._clear_all_pending:
                return DiscordResponse("No memory clear operation is waiting for confirmation.")
            deleted = self.clear_all_memories()
            self._clear_all_pending = False
            return DiscordResponse(f"Cleared {len(deleted)} memory item(s).")

        if self._is_pending_action_list_request(cleaned_prompt):
            return DiscordResponse(self._format_pending_actions(self._action_store.list_pending()))

        confirm_action_id = self._extract_confirm_action_id(cleaned_prompt)
        if confirm_action_id is not None:
            return DiscordResponse(self._execute_pending_action(confirm_action_id))

        cancel_action_id = self._extract_cancel_action_id(cleaned_prompt)
        if cancel_action_id is not None:
            return DiscordResponse(self._cancel_pending_action(cancel_action_id))

        if self._is_memory_list_request(cleaned_prompt):
            return DiscordResponse(self._format_memories(self.list_memories(limit=20)))

        if self._is_clear_all_request(cleaned_prompt):
            memory_count = self._memory_store.count()
            if memory_count == 0:
                return DiscordResponse("No memories stored.")
            self._clear_all_pending = True
            return DiscordResponse(
                f"This will delete all {memory_count} memory item(s). "
                "To confirm, send `/ask \u786e\u8ba4\u5220\u9664\u6240\u6709\u8bb0\u5fc6`."
            )

        memory_content = self._extract_memory_request(cleaned_prompt)
        if memory_content:
            memory = self.remember(memory_content)
            return DiscordResponse(f"Stored memory {memory.id}: {memory.content}")

        forget_query = self._extract_forget_request(cleaned_prompt)
        if forget_query:
            deleted = self.forget_memories_matching(forget_query)
            if not deleted:
                return DiscordResponse(f"No matching memories found for: {forget_query}")
            deleted_lines = "\n".join(f"- {memory.content}" for memory in deleted)
            return DiscordResponse(
                f"Forgot {len(deleted)} matching memory item(s):\n{deleted_lines}"
            )

        file_action = self._parse_file_action(cleaned_prompt)
        if file_action:
            action = self._action_store.create(file_action[0], file_action[1])
            return DiscordResponse(self._format_pending_action(action))

        if is_repo_analysis_request(cleaned_prompt):
            agent = RepoAnalysisAgent(self._llm_provider, self._settings)
            answer, trace = await agent.analyze(cleaned_prompt)
            trace_text = f"Tool trace:\n{trace.to_markdown()}"
            max_answer_length = 1900 - len(trace_text)
            if len(answer) > max_answer_length:
                answer = answer[:max_answer_length].rstrip() + "\n...[truncated]"
            return DiscordResponse(f"{answer}\n\n{trace_text}")

        messages = [
            ChatMessage(
                role="system",
                content=self._build_system_prompt(cleaned_prompt),
            ),
            ChatMessage(role="user", content=cleaned_prompt),
        ]
        answer = await self._llm_provider.chat(messages, model=self._settings.model)
        return DiscordResponse(answer)

    def remember(
        self,
        content: str,
        *,
        scope: str = "user",
        source: str = "discord",
    ) -> MemoryRecord:
        return self._memory_store.remember(content, scope=scope, source=source)

    def list_memories(self, *, limit: int = 10) -> list[MemoryRecord]:
        return self._memory_store.list_memories(limit=limit)

    def search_memories(self, query: str, *, limit: int = 10) -> list[MemoryRecord]:
        return self._memory_store.search(query, limit=limit)

    def forget_memory(self, memory_id: int) -> bool:
        return self._memory_store.forget(memory_id)

    def forget_memories_matching(self, query: str, *, limit: int = 10) -> list[MemoryRecord]:
        return self._memory_store.forget_matching(query, limit=limit)

    def clear_all_memories(self) -> list[MemoryRecord]:
        return self._memory_store.clear_all()

    async def handle_status(self) -> DiscordResponse:
        return DiscordResponse(
            "\n".join(
                [
                    "OscAgent status",
                    f"- environment: {self._settings.env}",
                    f"- model: {self._settings.model}",
                    f"- memories: {self._memory_store.count()}",
                    f"- pending actions: {len(self._action_store.list_pending())}",
                    f"- discord configured: {self._settings.discord_bot_token is not None}",
                    f"- OpenAI configured: {self._settings.openai_api_key is not None}",
                    f"- DeepSeek configured: {self._settings.deepseek_api_key is not None}",
                ]
            )
        )

    def _build_system_prompt(self, prompt: str) -> str:
        base_prompt = (
            "You are OscAgent, a concise research and coding assistant running from "
            "a Discord-first agent runtime. Persistent memory is authoritative for "
            "questions about the user. If the memory answers the question, answer from "
            "memory directly instead of saying you do not know."
        )
        memories = self._memory_store.context_memories(prompt, search_limit=10, recent_limit=20)
        if not memories:
            return base_prompt

        memory_lines = [f"- [{memory.scope}] {memory.content}" for memory in memories]
        return "\n".join(
            [
                base_prompt,
                "Relevant persistent memory:",
                *memory_lines,
            ]
        )

    def _extract_memory_request(self, prompt: str) -> str | None:
        patterns = (
            r"^(?:\u8bf7)?(?:\u5e2e\u6211)?\u8bb0\u4f4f[:\uff1a\s]*(.+)$",
            r"^(?:please\s+)?remember[:\s]+(.+)$",
        )
        for pattern in patterns:
            match = re.match(pattern, prompt, flags=re.IGNORECASE)
            if match:
                content = match.group(1).strip()
                return content or None
        return None

    def _extract_forget_request(self, prompt: str) -> str | None:
        patterns = (
            r"^(?:\u8bf7)?(?:\u5e2e\u6211)?\u5fd8\u8bb0[:\uff1a\s]*(.+)$",
            r"^(?:\u8bf7)?(?:\u5e2e\u6211)?\u5220\u9664(?:\u8bb0\u5fc6)?[:\uff1a\s]*(.+)$",
            r"^(?:please\s+)?forget[:\s]+(.+)$",
            r"^(?:please\s+)?delete\s+(?:the\s+)?memory\s+(?:about\s+)?(.+)$",
        )
        for pattern in patterns:
            match = re.match(pattern, prompt, flags=re.IGNORECASE)
            if match:
                content = match.group(1).strip()
                return content or None
        return None

    def _is_memory_list_request(self, prompt: str) -> bool:
        patterns = (
            r"^(?:\u6211|\u4f60)?\u8bb0\u5f97\u4ec0\u4e48[?\uff1f]?$",
            r"^\u5217\u51fa(?:\u6240\u6709)?\u8bb0\u5fc6$",
            r"^\u67e5\u770b(?:\u6240\u6709)?\u8bb0\u5fc6$",
            r"^(?:list|show)\s+(?:all\s+)?memories$",
            r"^what\s+do\s+you\s+remember\??$",
        )
        return any(re.match(pattern, prompt, flags=re.IGNORECASE) for pattern in patterns)

    def _is_clear_all_request(self, prompt: str) -> bool:
        patterns = (
            r"^(?:\u8bf7)?(?:\u5e2e\u6211)?(?:\u5220\u9664|\u6e05\u7a7a)\u6240\u6709\u8bb0\u5fc6$",
            r"^(?:\u8bf7)?(?:\u5e2e\u6211)?(?:\u5220\u9664|\u6e05\u7a7a)\u5168\u90e8\u8bb0\u5fc6$",
            r"^(?:clear|delete|forget)\s+(?:all\s+)?(?:memories|memory|everything)$",
        )
        return any(re.match(pattern, prompt, flags=re.IGNORECASE) for pattern in patterns)

    def _is_clear_all_confirmation(self, prompt: str) -> bool:
        patterns = (
            r"^\u786e\u8ba4(?:\u5220\u9664|\u6e05\u7a7a)(?:\u6240\u6709|\u5168\u90e8)\u8bb0\u5fc6$",
            r"^confirm\s+(?:clear|delete|forget)\s+(?:all\s+)?(?:memories|memory)$",
        )
        return any(re.match(pattern, prompt, flags=re.IGNORECASE) for pattern in patterns)

    def _extract_confirm_action_id(self, prompt: str) -> int | None:
        patterns = (
            r"^\u786e\u8ba4\u6267\u884c\s*pa_(\d+)$",
            r"^confirm\s+(?:execute\s+)?pa_(\d+)$",
        )
        return self._extract_action_id(prompt, patterns)

    def _extract_cancel_action_id(self, prompt: str) -> int | None:
        patterns = (
            r"^\u53d6\u6d88\s*pa_(\d+)$",
            r"^cancel\s+pa_(\d+)$",
        )
        return self._extract_action_id(prompt, patterns)

    def _extract_action_id(self, prompt: str, patterns: tuple[str, ...]) -> int | None:
        for pattern in patterns:
            match = re.match(pattern, prompt, flags=re.IGNORECASE)
            if match:
                return int(match.group(1))
        return None

    def _parse_file_action(self, prompt: str) -> tuple[str, list[PendingOperation]] | None:
        create_dir_patterns = (
            r"^(?:\u8bf7)?(?:\u5e2e\u6211)?\u521b\u5efa\u6587\u4ef6\u5939\s+(.+)$",
            r"^(?:\u8bf7)?(?:\u5e2e\u6211)?\u521b\u5efa(?:\u4e00\u4e2a)?(?:\u540d\u4e3a|\u53eb)?\s*(.+?)\s*\u7684?\u6587\u4ef6\u5939$",
            r"^(?:create|make)\s+(?:directory|folder)\s+(.+)$",
        )
        for pattern in create_dir_patterns:
            match = re.match(pattern, prompt, flags=re.IGNORECASE)
            if match:
                path = self._clean_path(match.group(1))
                return (
                    f"Create directory `{path}`",
                    [PendingOperation("create_directory", {"path": path})],
                )

        copy_patterns = (
            r"^\u628a\s+(.+?)\s+\u590d\u5236\u5230\s+(.+)$",
            r"^copy\s+(.+?)\s+to\s+(.+)$",
        )
        for pattern in copy_patterns:
            match = re.match(pattern, prompt, flags=re.IGNORECASE)
            if match:
                source = self._clean_path(match.group(1))
                destination = self._clean_path(match.group(2))
                return (
                    f"Copy `{source}` to `{destination}`",
                    [PendingOperation("copy_file", {"source": source, "destination": destination})],
                )

        move_patterns = (
            r"^\u628a\s+(.+?)\s+\u79fb\u52a8\u5230\s+(.+)$",
            r"^move\s+(.+?)\s+to\s+(.+)$",
        )
        for pattern in move_patterns:
            match = re.match(pattern, prompt, flags=re.IGNORECASE)
            if match:
                source = self._clean_path(match.group(1))
                destination = self._clean_path(match.group(2))
                return (
                    f"Move `{source}` to `{destination}`",
                    [PendingOperation("move_file", {"source": source, "destination": destination})],
                )

        write_patterns = (
            r"^\u5199\u6587\u4ef6\s+(.+?)\s+\u5185\u5bb9\s+(.+)$",
            r"^(?:\u8bf7)?(?:\u5e2e\u6211)?\u521b\u5efa(?:\u4e00\u4e2a)?(?:\u540d\u4e3a|\u53eb)?\s*(.+?)\s*\u7684?\u6587\u4ef6[,\uff0c\s]*\u5185\u5bb9(?:\u662f)?\s+(.+)$",
            r"^(?:\u8bf7)?(?:\u5e2e\u6211)?\u521b\u5efa\s+(.+?)\s+\u5185\u5bb9(?:\u662f)?\s+(.+)$",
            r"^write\s+file\s+(.+?)\s+content\s+(.+)$",
            r"^create\s+(?:a\s+)?file\s+(.+?)\s+with\s+content\s+(.+)$",
        )
        for pattern in write_patterns:
            match = re.match(pattern, prompt, flags=re.IGNORECASE)
            if match:
                path = self._clean_path(match.group(1))
                content = match.group(2).strip()
                return (
                    f"Write file `{path}`",
                    [PendingOperation("write_file", {"path": path, "content": content})],
                )

        return None

    def _is_pending_action_list_request(self, prompt: str) -> bool:
        patterns = (
            r"^\u67e5\u770b(?:\u5f85\u786e\u8ba4|\u5f85\u6267\u884c)(?:\u4efb\u52a1|\u64cd\u4f5c)$",
            r"^\u5217\u51fa(?:\u5f85\u786e\u8ba4|\u5f85\u6267\u884c)(?:\u4efb\u52a1|\u64cd\u4f5c)$",
            r"^(?:list|show)\s+pending\s+(?:actions|tasks|operations)$",
            r"^pending\s+(?:actions|tasks|operations)$",
        )
        return any(re.match(pattern, prompt, flags=re.IGNORECASE) for pattern in patterns)

    def _clean_path(self, path: str) -> str:
        return path.strip().strip("`'\"")

    def _execute_pending_action(self, action_id: int) -> str:
        action = self._action_store.get(action_id)
        if not action:
            return f"Pending action pa_{action_id} not found."
        if action.status != "pending":
            return f"Pending action pa_{action_id} is already {action.status}."

        results: list[str] = []
        try:
            for operation in action.operations:
                tool = self._write_tools.get(operation.tool_name)
                result = tool.execute(operation.arguments)
                results.append(f"- {result.content}")
        except Exception as exc:  # noqa: BLE001 - execution errors should be visible to the user.
            return f"Failed to execute pa_{action_id}: {exc}"

        self._action_store.mark_status(action_id, "executed")
        return "\n".join([f"Executed pa_{action_id}:", *results])

    def _cancel_pending_action(self, action_id: int) -> str:
        action = self._action_store.get(action_id)
        if not action:
            return f"Pending action pa_{action_id} not found."
        if action.status != "pending":
            return f"Pending action pa_{action_id} is already {action.status}."
        self._action_store.mark_status(action_id, "cancelled")
        return f"Cancelled pa_{action_id}."

    def _format_pending_action(self, action: PendingAction) -> str:
        operation_lines = [
            f"- `{operation.tool_name}` {operation.arguments}"
            for operation in action.operations
        ]
        return "\n".join(
            [
                f"Pending action pa_{action.id}: {action.description}",
                "This will modify workspace files.",
                "Operations:",
                *operation_lines,
                f"Confirm: /ask \u786e\u8ba4\u6267\u884c pa_{action.id}",
                f"Cancel: /ask \u53d6\u6d88 pa_{action.id}",
            ]
        )

    def _format_pending_actions(self, actions: list[PendingAction]) -> str:
        if not actions:
            return "No pending actions."

        lines = ["Pending actions:"]
        for action in actions:
            lines.append(f"pa_{action.id}: {action.description}")
            for operation in action.operations:
                lines.append(f"- `{operation.tool_name}` {operation.arguments}")
        return "\n".join(lines)

    def _format_memories(self, memories: list[MemoryRecord]) -> str:
        if not memories:
            return "No memories stored."

        lines = ["Stored memories:"]
        lines.extend(f"{memory.id}. [{memory.scope}] {memory.content}" for memory in memories)
        return "\n".join(lines)

    def _build_write_tools(self) -> ToolRegistry:
        registry = ToolRegistry()
        registry.register(CreateDirectoryTool(self._workspace_root))
        registry.register(WriteFileTool(self._workspace_root))
        registry.register(CopyFileTool(self._workspace_root))
        registry.register(MoveFileTool(self._workspace_root))
        return registry
