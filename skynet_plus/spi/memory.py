from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from ..core.provider import Provider


@dataclass
class MemoryItem:
    content: str
    scope: dict = field(default_factory=dict)      # e.g. {"agent": ..., "user": ...}
    metadata: dict = field(default_factory=dict)
    at: float = field(default_factory=time.time)
    score: float | None = None                     # set on recall


class MemoryProvider(Provider):
    async def remember(self, item: MemoryItem) -> str:
        """Store; return the provider's id for it."""
        raise NotImplementedError

    async def recall(self, query: str, scope: dict | None = None, limit: int = 5) -> list[MemoryItem]:
        raise NotImplementedError

    async def forget(self, scope: dict | None = None) -> int:
        raise NotImplementedError
