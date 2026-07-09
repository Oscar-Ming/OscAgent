from __future__ import annotations

from pathlib import Path

import pytest

from oscagent.memory import MemoryStore


def test_remember_and_list_memories(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path / "memory.db")

    memory = store.remember("User prefers FastAPI.", scope="user")

    assert memory.id == 1
    assert memory.scope == "user"
    assert store.count() == 1
    assert store.list_memories()[0].content == "User prefers FastAPI."


def test_remember_rejects_empty_content(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path / "memory.db")

    with pytest.raises(ValueError, match="empty"):
        store.remember("   ")


def test_search_returns_relevant_memories(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path / "memory.db")
    store.remember("User applies to AI graduate programs.")
    store.remember("User prefers FastAPI and Python.")

    results = store.search("write AI graduate project summary")

    assert [memory.content for memory in results] == ["User applies to AI graduate programs."]


def test_search_matches_short_chinese_memory(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path / "memory.db")
    store.remember("我21岁")

    results = store.search("我几岁")

    assert results[0].content == "我21岁"


def test_context_memories_include_recent_memories(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path / "memory.db")
    memory = store.remember("User prefers concise answers.")

    results = store.context_memories("unrelated query")

    assert results[0].id == memory.id


def test_forget_deletes_memory(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path / "memory.db")
    memory = store.remember("Temporary memory.")

    assert store.forget(memory.id)
    assert store.count() == 0
    assert not store.forget(memory.id)
