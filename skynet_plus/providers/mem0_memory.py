"""Mem0 memory provider (SP-030).

A Skynet+ scope `{"agent": ..., "user": ..., "run": ...}` maps to Mem0's agent_id, user_id
and run_id. Mem0 needs at least one of them, so a scope with none uses the configured
default agent.

Defaults, when no `config` block is given: facts are extracted with `gpt-4o-mini`
(`llm_model` changes it), embeddings use OpenAI's small model, and vectors live under
the project's `.skynet/mem0` folder rather than Mem0's machine-wide `/tmp/qdrant`. If
the extraction model rejects a request, the text is stored as written and the run record
says so; memory never fails a run. Pass a full Mem0 `config` block to use anything else.
"""
from __future__ import annotations

import inspect
import logging
import os
from pathlib import Path
from typing import Any

os.environ.setdefault("MEM0_TELEMETRY", "False")   # Mem0 phones home unless told not to
from mem0 import AsyncMemory  # noqa: E402

from ..core.provider import Health, Manifest  # noqa: E402
from ..spi import MemoryItem, MemoryProvider  # noqa: E402

VERSION = "1.0.0"
_IDS = {"agent": "agent_id", "user": "user_id", "run": "run_id"}


class Mem0Memory(MemoryProvider):
    manifest = Manifest(id="mem0", capability="memory", version=VERSION,
                        provides={"recall": True, "persistent": True, "scoped": True, "temporal": False},
                        package="mem0", description="Mem0 memory: facts extracted and stored per agent, user and run")

    def __init__(self, config: dict | None = None) -> None:
        super().__init__(config)
        self.infer: bool = bool(self.config.get("infer", True))
        self.threshold: float = float(self.config.get("threshold", 0.1))
        self.default_scope: dict = dict(self.config.get("default_scope") or {"agent": "skynet"})
        self.mem0_config: dict = self.config.get("config") or self._default_config()
        self._memory: Any = None
        self._error: str | None = None
        self.warnings: list[str] = []
        if not self.config.get("verbose"):
            for name in ("mem0", "mem0.memory", "mem0.memory.main", "mem0.memory.utils", "mem0.llms", "mem0.embeddings"):
                logging.getLogger(name).setLevel(logging.ERROR)

    def _default_config(self) -> dict:
        project = self.config.get("__skynet__") or {}
        base = Path(project.get("config_dir") or Path.cwd())
        path = Path(self.config.get("path") or base / ".skynet" / "mem0")
        return {
            "llm": {"provider": "openai", "config": {"model": self.config.get("llm_model", "gpt-4o-mini"),
                                                     "temperature": float(self.config.get("llm_temperature", 0.1))}},
            "embedder": {"provider": "openai", "config": {"model": self.config.get("embedding_model", "text-embedding-3-small")}},
            "vector_store": {"provider": "qdrant", "config": {"path": str(path), "collection_name": self.config.get("collection", "skynet"),
                                                              "on_disk": True}},
        }

    def _ids(self, scope: dict | None) -> dict:
        ids = {_IDS[k]: str(v) for k, v in (scope or {}).items() if k in _IDS and v is not None}
        if not ids:
            ids = {_IDS[k]: str(v) for k, v in self.default_scope.items() if k in _IDS}
        return ids

    async def initialize(self) -> None:
        try:
            created = AsyncMemory.from_config(self.mem0_config)
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
        llm = (self.mem0_config.get("llm") or {}).get("config", {}).get("model", "mem0 default")
        store = (self.mem0_config.get("vector_store") or {}).get("config", {}).get("path", "mem0 default")
        return Health(ok=True, detail=f"Mem0 store reachable; extraction {'by ' + str(llm) if self.infer else 'off'}; vectors at {store}")

    async def remember(self, item: MemoryItem) -> str:
        ids = self._ids(item.scope)
        try:
            result = await self._memory.add(item.content, metadata=item.metadata or None, infer=self.infer, **ids)
        except Exception as exc:  # noqa: BLE001
            if not self.infer:
                raise
            warning = f"fact extraction failed ({type(exc).__name__}: {str(exc)[:120]}); stored the text as written"
            self.warnings.append(warning)
            logging.getLogger(__name__).warning(warning)
            result = await self._memory.add(item.content, metadata={**(item.metadata or {}), "raw": True}, infer=False, **ids)
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
