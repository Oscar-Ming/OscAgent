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

    assert results[0].content == "User applies to AI graduate programs."


def test_search_matches_short_chinese_memory(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path / "memory.db")
    store.remember("\u621121\u5c81")

    results = store.search("\u6211\u51e0\u5c81")

    assert results[0].content == "\u621121\u5c81"


def test_search_matches_chinese_height_memory(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path / "memory.db")
    store.remember("\u6211\u8eab\u9ad86\u82f1\u5c3a")

    results = store.search("\u6211\u8eab\u9ad8\u591a\u5c11")

    assert results[0].content == "\u6211\u8eab\u9ad86\u82f1\u5c3a"


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


def test_forget_matching_deletes_relevant_memory(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path / "memory.db")
    height = store.remember("\u6211\u8eab\u9ad86\u82f1\u5c3a")
    color = store.remember("\u6211\u559c\u6b22\u84dd\u8272")

    deleted = store.forget_matching("\u6211\u7684\u8eab\u9ad8")

    assert [memory.id for memory in deleted] == [height.id]
    remaining = store.list_memories()
    assert height.id not in {memory.id for memory in remaining}
    assert color.id in {memory.id for memory in remaining}


def test_clear_all_deletes_all_memories(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path / "memory.db")
    first = store.remember("First memory.")
    second = store.remember("Second memory.")

    deleted = store.clear_all()

    assert {memory.id for memory in deleted} == {first.id, second.id}
    assert store.count() == 0
