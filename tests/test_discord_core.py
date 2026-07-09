from __future__ import annotations

import asyncio
from pathlib import Path

from oscagent.config import Settings
from oscagent.discord_core import DiscordCommandHandler
from oscagent.llm import ChatMessage, MockLLMProvider
from oscagent.memory import MemoryStore


def build_handler() -> DiscordCommandHandler:
    settings = Settings(OSCAGENT_MODEL="mock:test-model")
    return DiscordCommandHandler(MockLLMProvider(), settings)


class RecordingProvider:
    def __init__(self) -> None:
        self.messages: list[ChatMessage] = []

    async def chat(self, messages: list[ChatMessage], *, model: str) -> str:
        self.messages = messages
        return "recorded response"


def build_memory_handler(tmp_path: Path) -> tuple[DiscordCommandHandler, RecordingProvider]:
    settings = Settings(OSCAGENT_MODEL="mock:test-model", OSCAGENT_DB_PATH=tmp_path / "test.db")
    provider = RecordingProvider()
    memory_store = MemoryStore(settings.db_path)
    return DiscordCommandHandler(provider, settings, memory_store), provider


def test_handle_ask_returns_mock_response() -> None:
    handler = build_handler()

    response = asyncio.run(handler.handle_ask("hello"))

    assert response.content == "[mock:mock:test-model] hello"


def test_handle_ask_rejects_empty_prompt() -> None:
    handler = build_handler()

    response = asyncio.run(handler.handle_ask("   "))

    assert "Please include a question" in response.content


def test_handle_status_reports_model() -> None:
    handler = build_handler()

    response = asyncio.run(handler.handle_status())

    assert "OscAgent status" in response.content
    assert "- model: mock:test-model" in response.content


def test_handle_ask_routes_repo_analysis() -> None:
    handler = build_handler()

    response = asyncio.run(handler.handle_ask("analyze repo"))

    assert "Tool trace:" in response.content
    assert "`list_files`" in response.content


def test_memory_methods_store_search_and_forget(tmp_path: Path) -> None:
    handler, _ = build_memory_handler(tmp_path)

    memory = handler.remember("User prefers Python for AI projects.")

    assert handler.list_memories()[0].id == memory.id
    assert handler.search_memories("Python AI")[0].id == memory.id
    assert handler.forget_memory(memory.id)


def test_handle_ask_includes_relevant_memory(tmp_path: Path) -> None:
    handler, provider = build_memory_handler(tmp_path)
    handler.remember("User prefers concise architecture summaries.")

    response = asyncio.run(handler.handle_ask("Please write an architecture summary."))

    assert response.content == "recorded response"
    assert "Relevant persistent memory" in provider.messages[0].content
    assert "concise architecture summaries" in provider.messages[0].content


def test_handle_ask_can_store_memory_from_natural_language(tmp_path: Path) -> None:
    handler, _ = build_memory_handler(tmp_path)

    response = asyncio.run(handler.handle_ask("\u8bb0\u4f4f\u6211\u8eab\u9ad86\u82f1\u5c3a"))

    assert "Stored memory" in response.content
    assert (
        handler.search_memories("\u6211\u8eab\u9ad8\u591a\u5c11")[0].content
        == "\u6211\u8eab\u9ad86\u82f1\u5c3a"
    )


def test_handle_ask_can_forget_memory_from_natural_language(tmp_path: Path) -> None:
    handler, _ = build_memory_handler(tmp_path)
    handler.remember("\u6211\u8eab\u9ad86\u82f1\u5c3a")
    handler.remember("\u6211\u559c\u6b22\u84dd\u8272")

    response = asyncio.run(handler.handle_ask("\u8bf7\u5fd8\u8bb0\u6211\u7684\u8eab\u9ad8"))

    assert "Forgot 1" in response.content
    remaining = [memory.content for memory in handler.list_memories()]
    assert "\u6211\u8eab\u9ad86\u82f1\u5c3a" not in remaining
    assert "\u6211\u559c\u6b22\u84dd\u8272" in remaining
