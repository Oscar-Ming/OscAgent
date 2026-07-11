from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from oscagent.actions.models import PendingAction, PendingOperation


class PendingActionStore:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._initialized = False

    def create(self, description: str, operations: list[PendingOperation]) -> PendingAction:
        if not operations:
            raise ValueError("Pending action must include at least one operation.")

        self._ensure_schema()
        serialized_operations = json.dumps(
            [
                {
                    "tool_name": operation.tool_name,
                    "arguments": operation.arguments,
                }
                for operation in operations
            ],
            ensure_ascii=False,
        )
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO pending_actions (description, operations, status)
                VALUES (?, ?, 'pending')
                """,
                (description.strip(), serialized_operations),
            )
            action_id = int(cursor.lastrowid)
            row = self._fetch_row(connection, action_id)

        return self._action_from_row(row)

    def get(self, action_id: int) -> PendingAction | None:
        self._ensure_schema()
        with self._connect() as connection:
            row = self._fetch_row(connection, action_id)
        return self._action_from_row(row) if row else None

    def list_pending(self, *, limit: int = 20) -> list[PendingAction]:
        self._ensure_schema()
        limit = max(1, min(limit, 100))
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, description, status, operations, created_at
                FROM pending_actions
                WHERE status = 'pending'
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._action_from_row(row) for row in rows]

    def mark_status(self, action_id: int, status: str) -> bool:
        if status not in {"pending", "executed", "cancelled"}:
            raise ValueError(f"Unsupported pending action status: {status}")

        self._ensure_schema()
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE pending_actions SET status = ? WHERE id = ?",
                (status, action_id),
            )
            return cursor.rowcount > 0

    def _ensure_schema(self) -> None:
        if self._initialized:
            return

        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS pending_actions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    description TEXT NOT NULL,
                    operations TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_pending_actions_status
                ON pending_actions(status)
                """
            )
        self._initialized = True

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self._db_path)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _fetch_row(self, connection: sqlite3.Connection, action_id: int) -> sqlite3.Row | None:
        return connection.execute(
            """
            SELECT id, description, status, operations, created_at
            FROM pending_actions
            WHERE id = ?
            """,
            (action_id,),
        ).fetchone()

    def _action_from_row(self, row: sqlite3.Row) -> PendingAction:
        operations_payload = json.loads(str(row["operations"]))
        operations = [
            PendingOperation(
                tool_name=str(operation["tool_name"]),
                arguments=dict(operation["arguments"]),
            )
            for operation in operations_payload
        ]
        return PendingAction(
            id=int(row["id"]),
            description=str(row["description"]),
            status=str(row["status"]),
            operations=operations,
            created_at=str(row["created_at"]),
        )
