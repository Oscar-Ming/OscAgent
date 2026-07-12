from __future__ import annotations

import asyncio
from pathlib import Path

from oscagent.actions import PendingActionStore
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
    action_store = PendingActionStore(settings.db_path)
    return DiscordCommandHandler(provider, settings, memory_store, action_store, tmp_path), provider


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


def test_handle_status_reports_pending_actions(tmp_path: Path) -> None:
    handler, _ = build_memory_handler(tmp_path)
    asyncio.run(handler.handle_ask("create folder docs"))

    response = asyncio.run(handler.handle_status())

    assert "- pending actions: 1" in response.content


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


def test_handle_ask_can_list_memories_from_natural_language(tmp_path: Path) -> None:
    handler, _ = build_memory_handler(tmp_path)
    handler.remember("\u6211\u559c\u6b22\u84dd\u8272")

    response = asyncio.run(handler.handle_ask("\u4f60\u8bb0\u5f97\u4ec0\u4e48"))

    assert "Stored memories:" in response.content
    assert "\u6211\u559c\u6b22\u84dd\u8272" in response.content


def test_handle_ask_requires_confirmation_before_clear_all_memories(tmp_path: Path) -> None:
    handler, _ = build_memory_handler(tmp_path)
    handler.remember("\u6211\u559c\u6b22\u84dd\u8272")
    handler.remember("\u621121\u5c81")

    warning = asyncio.run(handler.handle_ask("\u5220\u9664\u6240\u6709\u8bb0\u5fc6"))

    assert "To confirm" in warning.content
    assert handler.list_memories()

    confirmed = asyncio.run(handler.handle_ask("\u786e\u8ba4\u5220\u9664\u6240\u6709\u8bb0\u5fc6"))

    assert "Cleared 2" in confirmed.content
    assert not handler.list_memories()


def test_handle_ask_creates_directory_only_after_confirmation(tmp_path: Path) -> None:
    handler, _ = build_memory_handler(tmp_path)

    pending = asyncio.run(handler.handle_ask("create folder docs"))

    assert "Pending action pa_1" in pending.content
    assert not (tmp_path / "docs").exists()

    executed = asyncio.run(handler.handle_ask("confirm"))

    assert "Executed pa_1" in executed.content
    assert (tmp_path / "docs").is_dir()


def test_handle_ask_can_cancel_pending_file_action(tmp_path: Path) -> None:
    handler, _ = build_memory_handler(tmp_path)

    pending = asyncio.run(handler.handle_ask("create folder docs"))

    assert "Pending action pa_1" in pending.content
    cancelled = asyncio.run(handler.handle_ask("cancel pa_1"))

    assert "Cancelled pa_1" in cancelled.content
    assert not (tmp_path / "docs").exists()


def test_handle_ask_moves_file_after_confirmation(tmp_path: Path) -> None:
    handler, _ = build_memory_handler(tmp_path)
    (tmp_path / "draft.txt").write_text("draft", encoding="utf-8")

    pending = asyncio.run(handler.handle_ask("move draft.txt to archive/draft.txt"))

    assert "Pending action pa_1" in pending.content
    assert (tmp_path / "draft.txt").exists()

    executed = asyncio.run(handler.handle_ask("confirm pa_1"))

    assert "Executed pa_1" in executed.content
    assert not (tmp_path / "draft.txt").exists()
    assert (tmp_path / "archive" / "draft.txt").read_text(encoding="utf-8") == "draft"


def test_handle_ask_can_list_pending_actions(tmp_path: Path) -> None:
    handler, _ = build_memory_handler(tmp_path)
    asyncio.run(handler.handle_ask("create folder docs"))

    response = asyncio.run(handler.handle_ask("list pending actions"))

    assert "Pending actions:" in response.content
    assert "pa_1: Create directory `docs`" in response.content


def test_handle_ask_writes_file_from_natural_language_after_confirmation(
    tmp_path: Path,
) -> None:
    handler, _ = build_memory_handler(tmp_path)

    pending = asyncio.run(
        handler.handle_ask("create a file scratch/test.txt with content hello")
    )

    assert "Pending action pa_1" in pending.content
    assert not (tmp_path / "scratch" / "test.txt").exists()

    executed = asyncio.run(handler.handle_ask("confirm pa_1"))

    assert "Executed pa_1" in executed.content
    assert (tmp_path / "scratch" / "test.txt").read_text(encoding="utf-8") == "hello"


def test_handle_ask_rejects_implicit_confirm_when_multiple_actions_exist(
    tmp_path: Path,
) -> None:
    handler, _ = build_memory_handler(tmp_path)
    asyncio.run(handler.handle_ask("create folder docs"))
    asyncio.run(handler.handle_ask("create folder notes"))

    response = asyncio.run(handler.handle_ask("confirm"))

    assert "Multiple pending actions exist" in response.content
    assert not (tmp_path / "docs").exists()
    assert not (tmp_path / "notes").exists()


def test_handle_ask_can_cancel_single_pending_action_implicitly(tmp_path: Path) -> None:
    handler, _ = build_memory_handler(tmp_path)
    asyncio.run(handler.handle_ask("create folder docs"))

    response = asyncio.run(handler.handle_ask("cancel"))

    assert "Cancelled pa_1" in response.content
    assert not (tmp_path / "docs").exists()


def test_handle_ask_writes_file_from_chinese_natural_language(tmp_path: Path) -> None:
    handler, _ = build_memory_handler(tmp_path)

    pending = asyncio.run(
        handler.handle_ask(
            "\u521b\u5efa\u4e00\u4e2a\u53eb scratch/test.txt "
            "\u7684\u6587\u4ef6\uff0c\u5185\u5bb9\u662f hello"
        )
    )

    assert "Pending action pa_1" in pending.content
    executed = asyncio.run(handler.handle_ask("confirm pa_1"))

    assert "Executed pa_1" in executed.content
    assert (tmp_path / "scratch" / "test.txt").read_text(encoding="utf-8") == "hello"


def test_handle_ask_plans_file_organization_before_confirmation(tmp_path: Path) -> None:
    handler, _ = build_memory_handler(tmp_path)
    (tmp_path / "scratch").mkdir()
    (tmp_path / "scratch" / "a.txt").write_text("a", encoding="utf-8")
    (tmp_path / "scratch" / "b.txt").write_text("b", encoding="utf-8")
    (tmp_path / "scratch" / "c.md").write_text("c", encoding="utf-8")

    pending = asyncio.run(handler.handle_ask("organize txt files in scratch to archive"))

    assert "Pending action pa_1" in pending.content
    assert "Organize txt files" in pending.content
    assert pending.content.count("`move_file`") == 2
    assert (tmp_path / "scratch" / "a.txt").exists()
    assert not (tmp_path / "archive" / "a.txt").exists()

    executed = asyncio.run(handler.handle_ask("confirm"))

    assert "Executed pa_1" in executed.content
    assert not (tmp_path / "scratch" / "a.txt").exists()
    assert not (tmp_path / "scratch" / "b.txt").exists()
    assert (tmp_path / "scratch" / "c.md").exists()
    assert (tmp_path / "archive" / "a.txt").read_text(encoding="utf-8") == "a"
    assert (tmp_path / "archive" / "b.txt").read_text(encoding="utf-8") == "b"


def test_handle_ask_reports_no_matching_files_for_organization(tmp_path: Path) -> None:
    handler, _ = build_memory_handler(tmp_path)
    (tmp_path / "scratch").mkdir()
    (tmp_path / "scratch" / "a.md").write_text("a", encoding="utf-8")

    response = asyncio.run(handler.handle_ask("organize txt files in scratch to archive"))

    assert response.content == "No matching files found for that organization request."
