from __future__ import annotations

import re
import sqlite3
from pathlib import Path

from oscagent.memory.models import MemoryRecord

TOKEN_PATTERN = re.compile(r"[\w\u4e00-\u9fff]+", re.IGNORECASE)


class MemoryStore:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._initialized = False

    def remember(
        self,
        content: str,
        *,
        scope: str = "user",
        source: str = "manual",
    ) -> MemoryRecord:
        cleaned_content = content.strip()
        if not cleaned_content:
            raise ValueError("Memory content cannot be empty.")

        self._ensure_schema()
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO memories (scope, content, source)
                VALUES (?, ?, ?)
                """,
                (scope, cleaned_content, source),
            )
            memory_id = int(cursor.lastrowid)
            row = connection.execute(
                """
                SELECT id, scope, content, source, created_at
                FROM memories
                WHERE id = ?
                """,
                (memory_id,),
            ).fetchone()

        return self._record_from_row(row)

    def list_memories(self, *, scope: str | None = None, limit: int = 20) -> list[MemoryRecord]:
        self._ensure_schema()
        limit = max(1, min(limit, 100))

        with self._connect() as connection:
            if scope:
                rows = connection.execute(
                    """
                    SELECT id, scope, content, source, created_at
                    FROM memories
                    WHERE scope = ?
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (scope, limit),
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT id, scope, content, source, created_at
                    FROM memories
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()

        return [self._record_from_row(row) for row in rows]

    def forget(self, memory_id: int) -> bool:
        self._ensure_schema()
        with self._connect() as connection:
            cursor = connection.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
            return cursor.rowcount > 0

    def search(self, query: str, *, limit: int = 5) -> list[MemoryRecord]:
        self._ensure_schema()
        limit = max(1, min(limit, 20))
        query_tokens = self._tokens(query)
        if not query_tokens:
            return []

        memories = self.list_memories(limit=100)
        scored: list[tuple[int, MemoryRecord]] = []
        for memory in memories:
            memory_tokens = self._tokens(memory.content)
            score = len(query_tokens & memory_tokens)
            if score:
                scored.append((score, memory))

        scored.sort(key=lambda item: (item[0], item[1].id), reverse=True)
        return [memory for _, memory in scored[:limit]]

    def context_memories(
        self,
        query: str,
        *,
        search_limit: int = 5,
        recent_limit: int = 3,
    ) -> list[MemoryRecord]:
        searched = self.search(query, limit=search_limit)
        recent = self.list_memories(limit=recent_limit)

        combined: list[MemoryRecord] = []
        seen_ids: set[int] = set()
        for memory in [*searched, *recent]:
            if memory.id in seen_ids:
                continue
            combined.append(memory)
            seen_ids.add(memory.id)

        return combined

    def count(self) -> int:
        self._ensure_schema()
        with self._connect() as connection:
            row = connection.execute("SELECT COUNT(*) FROM memories").fetchone()
        return int(row[0])

    def _ensure_schema(self) -> None:
        if self._initialized:
            return

        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    scope TEXT NOT NULL DEFAULT 'user',
                    content TEXT NOT NULL,
                    source TEXT NOT NULL DEFAULT 'manual',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_memories_scope
                ON memories(scope)
                """
            )
        self._initialized = True

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _record_from_row(self, row: sqlite3.Row) -> MemoryRecord:
        return MemoryRecord(
            id=int(row["id"]),
            scope=str(row["scope"]),
            content=str(row["content"]),
            source=str(row["source"]),
            created_at=str(row["created_at"]),
        )

    def _tokens(self, text: str) -> set[str]:
        tokens: set[str] = set()
        for match in TOKEN_PATTERN.finditer(text):
            token = match.group(0).lower()
            tokens.add(token)
            tokens.update(re.findall(r"\d+", token))
            tokens.update(char for char in token if "\u4e00" <= char <= "\u9fff")
        return tokens
