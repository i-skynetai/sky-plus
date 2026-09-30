"""System-1 decisions: a state, named typed questions, calibrated answers.

This contract mirrors the Praxis redesign so the Praxis adapter is a field mapping. The
vendor-neutral yes/no type is `boolean`; adapters may accept `noul` as an alias.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..core.provider import Provider

QUESTION_TYPES = ("choice", "score", "boolean", "rank")


@dataclass(frozen=True)
class Question:
    type: str
    instructions: str
    options: dict[str, str] = field(default_factory=dict)    # choice, rank: key -> description
    levels: tuple[str, ...] = ()                              # score: ordered low -> high

    def __post_init__(self) -> None:
        t = "boolean" if self.type == "noul" else self.type
        object.__setattr__(self, "type", t)
        if t not in QUESTION_TYPES:
            raise ValueError(f"question type must be one of {QUESTION_TYPES}, got {self.type!r}")
        if t in ("choice", "rank") and len(self.options) < 2:
            raise ValueError(f"{t} needs at least two options")
        if t == "score" and len(self.levels) < 2:
            raise ValueError("score needs at least two ordered levels")


@dataclass(frozen=True)
class DecisionRequest:
    capability: str
    state: Any
    questions: dict[str, Question]
    context: dict = field(default_factory=dict)


@dataclass
class DecisionResult:
    name: str
    answer: Any                          # option key | level | bool | list of keys
    distribution: dict[str, float]
    confidence: float                    # Skynet+ scale: 1 - normalised entropy
    abstain: bool
    answered_by: str = "system1"         # system1 | system2
    calibrated: bool = False
    native_confidence: float | None = None
    provider: str = ""
    model: str = ""
    version: str = ""
    latency_ms: int = 0
    cost_usd: float = 0.0
    trace_id: str | None = None


class DecisionProvider(Provider):
    async def decide(self, request: DecisionRequest) -> dict[str, DecisionResult]:
        """One result per question name. Never raises for an unsure answer: it abstains."""
        raise NotImplementedError
