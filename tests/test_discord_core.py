from __future__ import annotations

import asyncio

from oscagent.config import Settings
from oscagent.discord_core import DiscordCommandHandler
from oscagent.llm import MockLLMProvider


def build_handler() -> DiscordCommandHandler:
    settings = Settings(OSCAGENT_MODEL="mock:test-model")
    return DiscordCommandHandler(MockLLMProvider(), settings)


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
