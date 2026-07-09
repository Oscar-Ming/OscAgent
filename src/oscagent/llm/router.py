from __future__ import annotations

from dataclasses import dataclass

from oscagent.config import Settings
from oscagent.llm.base import ChatMessage
from oscagent.llm.mock import MockLLMProvider
from oscagent.llm.openai_compatible import OpenAICompatibleConfig, OpenAICompatibleProvider


@dataclass(frozen=True)
class ModelRoute:
    provider: str
    model: str


def parse_model_route(model: str) -> ModelRoute:
    provider, separator, model_name = model.partition(":")
    if not separator or not provider.strip() or not model_name.strip():
        raise ValueError("Model must use the '<provider>:<model>' format.")

    return ModelRoute(provider=provider.strip().lower(), model=model_name.strip())


class LLMRouter:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or Settings()
        self._mock_provider = MockLLMProvider()

    async def chat(self, messages: list[ChatMessage], *, model: str) -> str:
        route = parse_model_route(model)

        if route.provider == "mock":
            return await self._mock_provider.chat(messages, model=model)

        if route.provider == "openai":
            if not self._settings.openai_api_key:
                raise RuntimeError("OPENAI_API_KEY is required for openai models.")
            provider = OpenAICompatibleProvider(
                OpenAICompatibleConfig(
                    provider_name="OpenAI",
                    api_key=self._settings.openai_api_key,
                    base_url=self._settings.openai_base_url,
                    proxy=self._settings.llm_proxy,
                )
            )
            return await provider.chat(messages, model=route.model)

        if route.provider == "deepseek":
            if not self._settings.deepseek_api_key:
                raise RuntimeError("DEEPSEEK_API_KEY is required for deepseek models.")
            provider = OpenAICompatibleProvider(
                OpenAICompatibleConfig(
                    provider_name="DeepSeek",
                    api_key=self._settings.deepseek_api_key,
                    base_url=self._settings.deepseek_base_url,
                    proxy=self._settings.llm_proxy,
                )
            )
            return await provider.chat(messages, model=route.model)

        raise RuntimeError(f"Unsupported LLM provider: {route.provider}")
