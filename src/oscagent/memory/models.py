from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MemoryRecord:
    id: int
    scope: str
    content: str
    source: str
    created_at: str
