from __future__ import annotations

from dataclasses import dataclass

from oscagent.config import Settings
from oscagent.llm import ChatMessage, LLMProvider


@dataclass(frozen=True)
class DiscordResponse:
    content: str


class DiscordCommandHandler:
    def __init__(self, llm_provider: LLMProvider, settings: Settings | None = None) -> None:
        self._llm_provider = llm_provider
        self._settings = settings or Settings()

    async def handle_ask(self, prompt: str) -> DiscordResponse:
        cleaned_prompt = prompt.strip()
        if not cleaned_prompt:
            return DiscordResponse("Please include a question after `/ask`.")

        messages = [
            ChatMessage(
                role="system",
                content=(
                    "You are OscAgent, a concise research and coding assistant running from "
                    "a Discord-first agent runtime."
                ),
            ),
            ChatMessage(role="user", content=cleaned_prompt),
        ]
        answer = await self._llm_provider.chat(messages, model=self._settings.model)
        return DiscordResponse(answer)

    async def handle_status(self) -> DiscordResponse:
        return DiscordResponse(
            "\n".join(
                [
                    "OscAgent status",
                    f"- environment: {self._settings.env}",
                    f"- model: {self._settings.model}",
                    f"- discord configured: {self._settings.discord_bot_token is not None}",
                    f"- OpenAI configured: {self._settings.openai_api_key is not None}",
                    f"- DeepSeek configured: {self._settings.deepseek_api_key is not None}",
                ]
            )
        )
