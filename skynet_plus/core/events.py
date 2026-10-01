"""A tiny synchronous event bus. The kernel emits; anything may subscribe."""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from typing import Any


class EventBus:
    def __init__(self) -> None:
        self._subs: dict[str, list[Callable[..., Any]]] = defaultdict(list)
        self.history: list[tuple[str, dict]] = []

    def subscribe(self, kind: str, fn: Callable[..., Any]) -> None:
        self._subs[kind].append(fn)

    def emit(self, kind: str, **data: Any) -> None:
        self.history.append((kind, data))
        for fn in self._subs.get(kind, []) + self._subs.get("*", []):
            fn(kind, **data)
