"""Capabilities the local profile does not use yet. Interfaces only, so the taxonomy is complete."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..core.provider import Provider


@dataclass
class Authorization:
    decision: str            # allow | deny | needs_approval
    reason: str = ""


class AuthorizationProvider(Provider):
    async def authorize(self, action: str, context: dict | None = None) -> Authorization:
        raise NotImplementedError


class WorkflowProvider(Provider):
    async def start(self, workflow: str, payload: dict) -> str:
        raise NotImplementedError

    async def signal(self, workflow_id: str, name: str, payload: dict) -> None:
        raise NotImplementedError

    async def status(self, workflow_id: str) -> dict:
        raise NotImplementedError


@dataclass
class KnowledgeHit:
    content: str
    source: str = ""
    score: float = 0.0
    metadata: dict = field(default_factory=dict)


class KnowledgeProvider(Provider):
    async def search(self, query: str, scope: dict | None = None, limit: int = 5) -> list[KnowledgeHit]:
        raise NotImplementedError


class CodeIntelligenceProvider(Provider):
    async def find_symbols(self, query: str, repo: str | None = None) -> list[dict]:
        raise NotImplementedError

    async def read_source(self, path: str, start: int | None = None, end: int | None = None) -> str:
        raise NotImplementedError


class PaymentProvider(Provider):
    async def pay(self, amount: float, currency: str, to: str, context: dict | None = None) -> dict:
        raise NotImplementedError
