from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ChatMessage:
    role: str
    content: str


class LLMProvider(Protocol):
    async def chat(self, messages: list[ChatMessage], *, model: str) -> str:
        """Return a model response for the provided chat messages."""
