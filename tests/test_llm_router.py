from __future__ import annotations

import asyncio

import pytest

from oscagent.config import Settings
from oscagent.llm import ChatMessage, LLMRouter, parse_model_route


def test_parse_model_route() -> None:
    route = parse_model_route("openai:gpt-4.1-mini")

    assert route.provider == "openai"
    assert route.model == "gpt-4.1-mini"


def test_parse_model_route_rejects_invalid_format() -> None:
    with pytest.raises(ValueError, match="provider"):
        parse_model_route("gpt-4.1-mini")


def test_router_uses_mock_provider() -> None:
    settings = Settings(OSCAGENT_MODEL="mock:local")
    router = LLMRouter(settings)

    response = asyncio.run(
        router.chat([ChatMessage(role="user", content="hello")], model=settings.model)
    )

    assert response == "[mock:mock:local] hello"


def test_router_requires_openai_key() -> None:
    settings = Settings(OSCAGENT_MODEL="openai:gpt-4.1-mini", OPENAI_API_KEY=None)
    router = LLMRouter(settings)

    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        asyncio.run(router.chat([ChatMessage(role="user", content="hello")], model=settings.model))


def test_router_requires_deepseek_key() -> None:
    settings = Settings(OSCAGENT_MODEL="deepseek:deepseek-chat", DEEPSEEK_API_KEY=None)
    router = LLMRouter(settings)

    with pytest.raises(RuntimeError, match="DEEPSEEK_API_KEY"):
        asyncio.run(router.chat([ChatMessage(role="user", content="hello")], model=settings.model))
