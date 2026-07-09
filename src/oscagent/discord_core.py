from __future__ import annotations

import re
from dataclasses import dataclass

from oscagent.agent import RepoAnalysisAgent, is_repo_analysis_request
from oscagent.config import Settings
from oscagent.llm import ChatMessage, LLMProvider
from oscagent.memory import MemoryRecord, MemoryStore


@dataclass(frozen=True)
class DiscordResponse:
    content: str


class DiscordCommandHandler:
    def __init__(
        self,
        llm_provider: LLMProvider,
        settings: Settings | None = None,
        memory_store: MemoryStore | None = None,
    ) -> None:
        self._llm_provider = llm_provider
        self._settings = settings or Settings()
        self._memory_store = memory_store or MemoryStore(self._settings.db_path)

    async def handle_ask(self, prompt: str) -> DiscordResponse:
        cleaned_prompt = prompt.strip()
        if not cleaned_prompt:
            return DiscordResponse("Please include a question after `/ask`.")

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

    async def handle_status(self) -> DiscordResponse:
        return DiscordResponse(
            "\n".join(
                [
                    "OscAgent status",
                    f"- environment: {self._settings.env}",
                    f"- model: {self._settings.model}",
                    f"- memories: {self._memory_store.count()}",
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
