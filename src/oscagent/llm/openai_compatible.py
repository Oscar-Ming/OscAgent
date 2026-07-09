from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Any

from oscagent.llm.base import ChatMessage


@dataclass(frozen=True)
class OpenAICompatibleConfig:
    provider_name: str
    api_key: str
    base_url: str
    proxy: str | None = None
    timeout_seconds: float = 60.0


class OpenAICompatibleProvider:
    def __init__(self, config: OpenAICompatibleConfig) -> None:
        self._config = config

    async def chat(self, messages: list[ChatMessage], *, model: str) -> str:
        try:
            import httpx
        except ImportError as exc:
            raise RuntimeError(
                'LLM support is not installed. Run: python -m pip install -e ".[llm]"'
            ) from exc

        request_body = {
            "model": model,
            "messages": [
                {
                    "role": message.role,
                    "content": message.content,
                }
                for message in messages
            ],
        }
        headers = {
            "Authorization": f"Bearer {self._config.api_key}",
            "Content-Type": "application/json",
        }
        client_kwargs: dict[str, Any] = {"timeout": self._config.timeout_seconds}
        if self._config.proxy:
            proxy_arg = (
                "proxy"
                if "proxy" in inspect.signature(httpx.AsyncClient).parameters
                else "proxies"
            )
            client_kwargs[proxy_arg] = self._config.proxy

        async with httpx.AsyncClient(**client_kwargs) as client:
            response = await client.post(
                f"{self._config.base_url.rstrip('/')}/chat/completions",
                headers=headers,
                json=request_body,
            )

        if response.status_code >= 400:
            raise RuntimeError(
                f"{self._config.provider_name} API request failed "
                f"with HTTP {response.status_code}: {response.text}"
            )

        payload = response.json()
        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(
                f"{self._config.provider_name} API returned an unexpected response."
            ) from exc

        if not isinstance(content, str):
            raise RuntimeError(f"{self._config.provider_name} API returned non-text content.")

        return content
