"""Mem0 memory provider (SP-030).

A Skynet+ scope `{"agent": ..., "user": ..., "run": ...}` maps to Mem0's agent_id, user_id
and run_id. Mem0 needs at least one of them, so a scope with none uses the configured
default agent. The embedder and LLM Mem0 uses come from its own config block.
"""
from __future__ import annotations

import inspect
import os
from typing import Any

os.environ.setdefault("MEM0_TELEMETRY", "False")   # Mem0 phones home unless told not to
from mem0 import AsyncMemory  # noqa: E402

from ..core.provider import Health, Manifest
from ..spi import MemoryItem, MemoryProvider

VERSION = "0.2.0"
_IDS = {"agent": "agent_id", "user": "user_id", "run": "run_id"}


class Mem0Memory(MemoryProvider):
    manifest = Manifest(id="mem0", capability="memory", version=VERSION,
                        provides={"recall": True, "persistent": True, "scoped": True, "temporal": False},
                        package="mem0", description="Mem0 memory: facts extracted and stored per agent, user and run")

    def __init__(self, config: dict | None = None) -> None:
        super().__init__(config)
        self.mem0_config: dict | None = self.config.get("config")
        self.infer: bool = bool(self.config.get("infer", True))
        self.threshold: float = float(self.config.get("threshold", 0.1))
        self.default_scope: dict = dict(self.config.get("default_scope") or {"agent": "skynet"})
        self._memory: Any = None
        self._error: str | None = None

    def _ids(self, scope: dict | None) -> dict:
        ids = {_IDS[k]: str(v) for k, v in (scope or {}).items() if k in _IDS and v is not None}
        if not ids:
            ids = {_IDS[k]: str(v) for k, v in self.default_scope.items() if k in _IDS}
        return ids

    async def initialize(self) -> None:
        try:
            if self.mem0_config:
                created = AsyncMemory.from_config(self.mem0_config)
            else:
                created = AsyncMemory()
            self._memory = await created if inspect.isawaitable(created) else created
        except Exception as exc:  # noqa: BLE001 — reported by health, never raised at start
            self._error = f"{type(exc).__name__}: {str(exc)[:200]}"

    async def health(self) -> Health:
        if self._memory is None:
            return Health(ok=False, detail=f"Mem0 could not start: {self._error or 'not initialised'}")
        try:
            await self._memory.get_all(filters=self._ids({"agent": "skynet-doctor"}), top_k=1)
        except Exception as exc:  # noqa: BLE001
            return Health(ok=False, detail=f"Mem0 store unreachable: {type(exc).__name__}: {str(exc)[:200]}")
        return Health(ok=True, detail="Mem0 store reachable" + ("" if self.infer else "; infer off"))

    async def remember(self, item: MemoryItem) -> str:
        result = await self._memory.add(item.content, metadata=item.metadata or None, infer=self.infer,
                                        **self._ids(item.scope))
        rows = result.get("results", []) if isinstance(result, dict) else (result or [])
        return str(rows[0].get("id", "")) if rows and isinstance(rows[0], dict) else ""

    async def recall(self, query: str, scope: dict | None = None, limit: int = 5) -> list[MemoryItem]:
        result = await self._memory.search(query, top_k=limit, filters=self._ids(scope), threshold=self.threshold)
        rows = result.get("results", []) if isinstance(result, dict) else (result or [])
        return [MemoryItem(content=str(r.get("memory", "")), scope=dict(scope or self.default_scope),
                           metadata=dict(r.get("metadata") or {}), score=r.get("score"))
                for r in rows if isinstance(r, dict)]

    async def forget(self, scope: dict | None = None) -> int:
        ids = self._ids(scope)
        before = await self._memory.get_all(filters=ids, top_k=10_000)
        rows = before.get("results", []) if isinstance(before, dict) else (before or [])
        await self._memory.delete_all(**ids)
        return len(rows)

    async def close(self) -> None:
        self._memory = None
