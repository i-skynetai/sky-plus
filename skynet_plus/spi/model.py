from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..core.provider import Provider


@dataclass
class ModelResponse:
    text: str
    model: str
    usage: dict = field(default_factory=dict)      # input_tokens, output_tokens, cost_usd
    structured: Any = None                         # parsed object when a schema was requested
    tool_calls: list[dict] = field(default_factory=list)   # [{"id", "name", "arguments"}]
    raw: Any = None


class ModelProvider(Provider):
    """A chat-completion gateway. Messages are plain dicts: {"role": ..., "content": ...}."""

    async def complete(self, messages: list[dict], *, schema: dict | None = None,
                       **options: Any) -> ModelResponse:
        raise NotImplementedError
