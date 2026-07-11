from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PendingOperation:
    tool_name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class PendingAction:
    id: int
    description: str
    status: str
    operations: list[PendingOperation]
    created_at: str
