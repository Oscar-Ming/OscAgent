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

    def forget_matching(self, query: str, *, limit: int = 10) -> list[MemoryRecord]:
        scored_matches = self._scored_memories(query)
        if not scored_matches:
            return []

        highest_score = scored_matches[0][0]
        if highest_score < 2:
            return []

        matches = [memory for score, memory in scored_matches[:limit] if score == highest_score]
        deleted: list[MemoryRecord] = []
        with self._connect() as connection:
            for memory in matches:
                cursor = connection.execute("DELETE FROM memories WHERE id = ?", (memory.id,))
                if cursor.rowcount:
                    deleted.append(memory)

        return deleted

    def search(self, query: str, *, limit: int = 5) -> list[MemoryRecord]:
        self._ensure_schema()
        limit = max(1, min(limit, 20))
        query_tokens = self._tokens(query)
        normalized_query = self._normalize(query)
        if not query_tokens and not normalized_query:
            return []

        memories = self.list_memories(limit=100)
        scored = [
            (self._score(query_tokens, normalized_query, memory), memory)
            for memory in memories
        ]
        scored = [(score, memory) for score, memory in scored if score]

        scored.sort(key=lambda item: (item[0], item[1].id), reverse=True)
        return [memory for _, memory in scored[:limit]]

    def context_memories(
        self,
        query: str,
        *,
        search_limit: int = 10,
        recent_limit: int = 20,
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

    def _normalize(self, text: str) -> str:
        return "".join(match.group(0).lower() for match in TOKEN_PATTERN.finditer(text))

    def _scored_memories(self, query: str) -> list[tuple[int, MemoryRecord]]:
        query_tokens = self._tokens(query)
        normalized_query = self._normalize(query)
        if not query_tokens and not normalized_query:
            return []

        scored = [
            (self._score(query_tokens, normalized_query, memory), memory)
            for memory in self.list_memories(limit=100)
        ]
        scored = [(score, memory) for score, memory in scored if score]
        scored.sort(key=lambda item: (item[0], item[1].id), reverse=True)
        return scored

    def _score(
        self,
        query_tokens: set[str],
        normalized_query: str,
        memory: MemoryRecord,
    ) -> int:
        memory_tokens = self._tokens(memory.content)
        normalized_memory = self._normalize(memory.content)
        score = len(query_tokens & memory_tokens)
        if normalized_query and normalized_memory:
            if normalized_query in normalized_memory or normalized_memory in normalized_query:
                score += 8
            score += len(set(normalized_query) & set(normalized_memory))
        return score
