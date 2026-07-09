from __future__ import annotations

from oscagent.llm.base import ChatMessage


class MockLLMProvider:
    async def chat(self, messages: list[ChatMessage], *, model: str) -> str:
        last_user_message = next(
            (message.content for message in reversed(messages) if message.role == "user"),
            "",
        )

        if not last_user_message.strip():
            return "Mock provider received an empty message."

        return f"[mock:{model}] {last_user_message}"
