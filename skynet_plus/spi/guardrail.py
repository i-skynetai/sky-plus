from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..core.provider import Provider

STAGES = ("input", "tool", "tool-result", "output")


@dataclass
class Verdict:
    action: str                 # allow | deny | modify
    reason: str = ""
    content: Any = None         # the modified content when action == "modify"

    @property
    def allowed(self) -> bool:
        return self.action in ("allow", "modify")


class GuardrailProvider(Provider):
    async def check(self, content: Any, stage: str, context: dict | None = None) -> Verdict:
        raise NotImplementedError
