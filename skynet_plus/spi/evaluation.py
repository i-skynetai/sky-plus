from __future__ import annotations

from dataclasses import dataclass, field

from ..core.provider import Provider


@dataclass
class EvalResult:
    scores: dict[str, float] = field(default_factory=dict)
    passed: bool | None = None
    detail: dict = field(default_factory=dict)


class EvaluationProvider(Provider):
    async def evaluate(self, run: dict, metrics: list[str] | None = None) -> EvalResult:
        """`run` is a run record dict (canonical, provider-neutral), never a framework trace."""
        raise NotImplementedError
