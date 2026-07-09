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
