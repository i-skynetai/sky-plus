"""A deterministic guardrail. No model, no network: patterns, tool lists and size limits.

This is the "deterministic policy" half of the guardrail capability. A semantic provider
(NeMo or another classifier) can sit beside it later; this one is always available.
"""
from __future__ import annotations

import json
import re
from typing import Any

from ..core.provider import Health, Manifest
from ..spi import GuardrailProvider, Verdict


class RulesGuardrail(GuardrailProvider):
    manifest = Manifest(id="rules", capability="guardrail", version="1.0.0",
                        provides={"input": True, "output": True, "tool": True, "deterministic": True},
                        description="deny patterns, tool allow/deny lists and a size limit; no model")
    DEFAULT_DENY = (r"rm\s+-rf", r"drop\s+table", r"format\s+c:", r"BEGIN (RSA|OPENSSH) PRIVATE KEY")

    def __init__(self, config: dict | None = None) -> None:
        super().__init__(config)
        self._patterns = [re.compile(p, re.IGNORECASE) for p in self.config.get("deny_patterns", self.DEFAULT_DENY)]
        self._max_chars = int(self.config.get("max_chars", 200_000))
        self._allow_tools = self.config.get("allow_tools")
        self._deny_tools = set(self.config.get("deny_tools", []))

    async def health(self) -> Health:
        return Health(ok=True, detail=f"{len(self._patterns)} patterns, max {self._max_chars} chars")

    async def check(self, content: Any, stage: str, context: dict | None = None) -> Verdict:
        size = len(content) if isinstance(content, str) else len(json.dumps(content, default=str))
        if size > self._max_chars:
            return Verdict("deny", f"{stage} content is {size} chars, limit {self._max_chars}")
        if stage == "tool" and isinstance(content, dict) and "tool" in content:
            name = content["tool"]
            if name in self._deny_tools:
                return Verdict("deny", f"tool {name!r} is on the deny list")
            if self._allow_tools is not None and name not in self._allow_tools:
                return Verdict("deny", f"tool {name!r} is not on the allow list")
        for text in _strings(content):            # every string inside, as written — no JSON escaping
            for pattern in self._patterns:
                if pattern.search(text):
                    return Verdict("deny", f"{stage} content matches denied pattern {pattern.pattern!r}")
        return Verdict("allow")


def _strings(value: Any):
    """Yield every string inside a nested structure (dict keys and values, lists, tuples)."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for k, v in value.items():
            yield from _strings(k)
            yield from _strings(v)
    elif isinstance(value, (list, tuple, set)):
        for v in value:
            yield from _strings(v)
    elif value is not None and not isinstance(value, (int, float, bool)):
        yield str(value)
