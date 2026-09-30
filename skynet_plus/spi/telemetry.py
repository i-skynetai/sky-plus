from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

from ..core.provider import Provider


class TelemetryProvider(Provider):
    @contextmanager
    def span(self, name: str, attributes: dict | None = None) -> Iterator[Any]:
        """Synchronous context manager so it wraps both sync and async code paths."""
        yield None

    async def emit(self, kind: str, **data: Any) -> None:
        raise NotImplementedError
