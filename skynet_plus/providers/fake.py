"""In-memory providers for every capability the local profile uses.

They exist so that a fresh clone runs `skynet doctor` and an `Agent.run()` with no installs
and no keys, and so the conformance tests have a reference implementation. They are
deterministic and honest about being fakes: the model does not think, it composes.
"""
from __future__ import annotations

import inspect
import json
import math
import re
import time
from collections.abc import Iterator
from contextlib import contextmanager, nullcontext
from typing import Any

from ..core.contracts import AgentSpec, Result, Step, Task
from ..core.provider import Health, Manifest
from ..core.runrecord import RecorderHandle
from ..spi import (
    AgentRuntimeProvider,
    Authorization,
    AuthorizationProvider,
    DecisionProvider,
    DecisionRequest,
    DecisionResult,
    EvalResult,
    EvaluationProvider,
    GuardrailProvider,
    MemoryItem,
    MemoryProvider,
    ModelProvider,
    ModelResponse,
    TelemetryProvider,
    Verdict,
)

VERSION = "1.0.0"
_WORD = re.compile(r"[a-z0-9]+")
_STOP = {"the", "a", "an", "to", "of", "is", "are", "was", "be", "do", "does", "this", "that",
         "and", "or", "please", "i", "my", "me", "it", "in", "on", "for", "with", "you", "your"}


def _stem(word: str) -> str:
    return word[:-1] if len(word) > 3 and word.endswith("s") else word


def _tokens(value: Any) -> set[str]:
    text = value.lower() if isinstance(value, str) else json.dumps(value, sort_keys=True).lower()
    return {_stem(w) for w in _WORD.findall(text) if w not in _STOP}


def _entropy_confidence(dist: dict[str, float]) -> float:
    n = len(dist)
    if n < 2:
        return 1.0
    h = -sum(p * math.log(p) for p in dist.values() if p > 0)
    return round(1.0 - h / math.log(n), 4)


class FakeModel(ModelProvider):
    manifest = Manifest(id="fake", capability="model", version=VERSION,
                        provides={"completion": True, "structured": True, "streaming": False},
                        description="composes a deterministic answer from the messages")

    async def complete(self, messages: list[dict], *, schema: dict | None = None, **options: Any) -> ModelResponse:
        system = next((m["content"] for m in messages if m.get("role") == "system"), "")
        user = [m["content"] for m in messages if m.get("role") == "user"]
        tool_results = [m["content"] for m in messages if m.get("role") == "tool"]
        parts = [f"[{self.manifest.ref}]"]
        if system:
            parts.append(f"following: {system.strip()[:60]}")
        if user:
            parts.append(f"task: {str(user[-1]).strip()[:80]}")
        if tool_results:
            parts.append(f"tool said: {str(tool_results[-1])[:80]}")
        text = " | ".join(parts)
        in_tokens = sum(len(str(m.get("content", ""))) for m in messages) // 4
        usage = {"input_tokens": in_tokens, "output_tokens": len(text) // 4, "cost_usd": 0.0}
        if schema and "action" in (schema.get("properties") or {}):
            # A planner asked for a proposal: use the tool named in the task once, then finish.
            tools: list[dict] = []
            for m in messages:
                if m.get("role") == "system" and "available_tools" in str(m.get("content", "")):
                    try:
                        tools = json.loads(m["content"]).get("available_tools", [])
                    except (json.JSONDecodeError, AttributeError):
                        tools = []
            task = str(user[-1]) if user else ""
            if tools and not tool_results:
                name = next((t["name"] for t in tools if t["name"].lower() in task.lower()), tools[0]["name"])
                structured: dict = {"action": "tool", "tool": name, "args": {"input": task}}
            else:
                structured = {"action": "final", "answer": text}
            return ModelResponse(text=json.dumps(structured), model="fake-1", usage=usage, structured=structured)
        plain: dict | None = {"answer": text} if schema else None
        return ModelResponse(text=text, model="fake-1", usage=usage, structured=plain)


class FakeMemory(MemoryProvider):
    manifest = Manifest(id="fake", capability="memory", version=VERSION,
                        provides={"recall": True, "persistent": False, "temporal": False},
                        description="a list in memory; recall by token overlap")

    def __init__(self, config: dict | None = None) -> None:
        super().__init__(config)
        self.items: list[MemoryItem] = []

    async def remember(self, item: MemoryItem) -> str:
        self.items.append(item)
        return f"mem-{len(self.items)}"

    async def recall(self, query: str, scope: dict | None = None, limit: int = 5) -> list[MemoryItem]:
        q = _tokens(query)
        scored = []
        for item in self.items:
            if scope and any(item.scope.get(k) != v for k, v in scope.items()):
                continue
            t = _tokens(item.content)
            union = len(q | t)
            score = len(q & t) / union if union else 0.0
            if score > 0:
                scored.append(MemoryItem(item.content, item.scope, item.metadata, item.at, round(score, 3)))
        scored.sort(key=lambda m: m.score or 0.0, reverse=True)
        return scored[:limit]

    async def forget(self, scope: dict | None = None) -> int:
        before = len(self.items)
        self.items = [i for i in self.items if scope and any(i.scope.get(k) != v for k, v in scope.items())]
        return before - len(self.items)


class FakeDecision(DecisionProvider):
    manifest = Manifest(id="fake", capability="decision", version=VERSION,
                        provides={"choice": True, "score": True, "boolean": True, "rank": True,
                                  "calibrated": False, "abstain": True},
                        description="token overlap between state and options; abstains below threshold")

    async def decide(self, request: DecisionRequest) -> dict[str, DecisionResult]:
        threshold = float(self.config.get("threshold", 0.5))
        state = _tokens(request.state)
        out: dict[str, DecisionResult] = {}
        for name, q in request.questions.items():
            started = time.time()
            # overlap cubed: a fake, but a sharp one, so a clear match clears the threshold
            if q.type in ("choice", "rank"):
                weights = {k: (1.0 + len(state & _tokens(f"{k} {d}"))) ** 3 for k, d in q.options.items()}
            elif q.type == "score":
                weights = {lvl: (1.0 + len(state & _tokens(lvl))) ** 3 for lvl in q.levels}
            else:
                yes = (1.0 + len(state & _tokens(q.instructions))) ** 3
                weights = {"true": yes, "false": 1.0}
            total = sum(weights.values())
            dist = {k: round(w / total, 4) for k, w in weights.items()}
            confidence = _entropy_confidence(dist)
            ranked = sorted(dist, key=lambda k: dist[k], reverse=True)
            if q.type == "rank":
                answer: Any = ranked
            elif q.type == "boolean":
                answer = dist["true"] > 0.5
            else:
                answer = ranked[0]
            out[name] = DecisionResult(name=name, answer=answer, distribution=dist,
                                       confidence=confidence, abstain=confidence < threshold,
                                       provider=self.manifest.id, model="overlap", version=VERSION,
                                       latency_ms=int((time.time() - started) * 1000))
        return out


class FakeGuardrail(GuardrailProvider):
    manifest = Manifest(id="fake", capability="guardrail", version=VERSION,
                        provides={"input": True, "output": True, "tool": True},
                        description="denies content matching configured patterns")
    DEFAULT_DENY = ("rm -rf", "drop table", "format c:")

    async def check(self, content: Any, stage: str, context: dict | None = None) -> Verdict:
        patterns = [p.lower() for p in self.config.get("deny_patterns", self.DEFAULT_DENY)]
        text = content if isinstance(content, str) else json.dumps(content, default=str)
        hit = next((p for p in patterns if p in text.lower()), None)
        if hit:
            return Verdict("deny", f"{stage} content matches denied pattern {hit!r}")
        return Verdict("allow")


class FakeAuthorization(AuthorizationProvider):
    manifest = Manifest(id="fake", capability="authorization", version=VERSION,
                        provides={"allow": True, "deny": True, "needs_approval": True},
                        description="allow-list, deny-list and approval-list of action names")

    async def authorize(self, action: str, context: dict | None = None) -> Authorization:
        if action in self.config.get("deny", []):
            return Authorization("deny", f"{action!r} is on the deny list")
        if action in self.config.get("needs_approval", []):
            return Authorization("needs_approval", f"{action!r} needs a human")
        allow = self.config.get("allow")
        if allow is not None and action not in allow:
            return Authorization("deny", f"{action!r} is not on the allow list")
        return Authorization("allow")


class FakeEvaluation(EvaluationProvider):
    manifest = Manifest(id="fake", capability="evaluation", version=VERSION,
                        provides={"outcome": True, "trajectory": False},
                        description="scores completion and step count from the run record")

    async def evaluate(self, run: dict, metrics: list[str] | None = None) -> EvalResult:
        result = run.get("result") or {}
        completed = 1.0 if result.get("status") == "ok" else 0.0
        steps = len(result.get("steps", []))
        return EvalResult(scores={"completed": completed, "steps": float(steps)}, passed=completed == 1.0)


class FakeTelemetry(TelemetryProvider):
    manifest = Manifest(id="fake", capability="telemetry", version=VERSION,
                        provides={"spans": True, "events": True},
                        description="keeps spans and events in a list")

    def __init__(self, config: dict | None = None) -> None:
        super().__init__(config)
        self.spans: list[dict] = []
        self.events: list[dict] = []

    @contextmanager
    def span(self, name: str, attributes: dict | None = None) -> Iterator[dict]:
        entry: dict[str, Any] = {"name": name, "attributes": dict(attributes or {}), "started": time.time()}
        self.spans.append(entry)
        try:
            yield entry
        finally:
            entry["duration_ms"] = int((time.time() - entry["started"]) * 1000)

    async def emit(self, kind: str, **data: Any) -> None:
        self.events.append({"kind": kind, **data})


class FakeAgentRuntime(AgentRuntimeProvider):
    """Propose → govern → execute → answer, using whatever services are configured."""
    manifest = Manifest(id="fake", capability="agent-runtime", version=VERSION,
                        provides={"agents": True, "streaming": False, "checkpointing": False, "hitl": True},
                        requires=("model",),
                        description="a deterministic single-step loop over the configured services")

    async def health(self) -> Health:
        return Health(ok=True, detail="in-memory")

    async def run(self, spec: AgentSpec, task: Task, services: Any, recorder: RecorderHandle) -> Result:
        steps: list[Step] = []
        served = services.refs()
        usage: dict[str, float] = {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}

        def step(kind: str, **detail: Any) -> None:
            steps.append(Step(kind, detail))
            recorder.event(kind, **detail)

        step("run.input", task=task.text, agent=spec.name)
        guardrail = services.get("guardrail")
        if guardrail:
            verdict = await guardrail.check(task.input, "input")
            step("guardrail.input", action=verdict.action, reason=verdict.reason)
            if not verdict.allowed:
                return Result(task.id, None, status="denied", steps=steps, served_by=served,
                              error=verdict.reason)
            if verdict.action == "modify":
                task = Task(verdict.content, id=task.id, metadata=task.metadata)
                step("guardrail.modified", stage="input")

        context: list[str] = []
        memory = services.get("memory")
        if memory:
            try:
                recalled = await memory.recall(task.text, scope={"agent": spec.name})
                context = [m.content for m in recalled]
                step("memory.recall", hits=len(recalled))
            except Exception as exc:  # noqa: BLE001 — memory is auxiliary; the run goes on without it
                step("memory.failed", stage="recall", error=f"{type(exc).__name__}: {str(exc)[:200]}")

        tool_result: Any = None
        if spec.tools:
            chosen = next((t for t in spec.tools if t.name.lower() in task.text.lower()), spec.tools[0])
            args: dict[str, Any] = {"input": task.text}
            step("action.proposed", tool=chosen.name, args=args)
            if guardrail:
                verdict = await guardrail.check({"tool": chosen.name, "args": args}, "tool")
                step("guardrail.tool", action=verdict.action, reason=verdict.reason)
                if not verdict.allowed:
                    return Result(task.id, None, status="denied", steps=steps, served_by=served,
                                  error=verdict.reason)
                if verdict.action == "modify" and isinstance(verdict.content, dict):
                    args = dict(verdict.content.get("args", verdict.content))
                    step("guardrail.modified", stage="tool", args=args)
            auth = services.get("authorization")
            if auth:
                decision = await auth.authorize(chosen.name, {"agent": spec.name, "task": task.id})
                step("authorization", action=chosen.name, decision=decision.decision, reason=decision.reason)
                if decision.decision == "needs_approval":
                    return Result(task.id, {"pending": chosen.name}, status="needs_approval",
                                  steps=steps, served_by=served, error=decision.reason)
                if decision.decision == "deny":
                    return Result(task.id, None, status="denied", steps=steps, served_by=served,
                                  error=decision.reason)
            telemetry = services.get("telemetry")
            span = telemetry.span(f"tool.{chosen.name}", {"tool": chosen.name}) if telemetry else nullcontext()
            try:
                with span:
                    tool_result = chosen.invoke(task=task, **args)
                    if inspect.isawaitable(tool_result):
                        tool_result = await tool_result
                step("tool.executed", tool=chosen.name, result=tool_result)
            except Exception as exc:  # noqa: BLE001
                step("tool.failed", tool=chosen.name, error=f"{type(exc).__name__}: {exc}")
                return Result(task.id, None, status="error", steps=steps, served_by=served,
                              error=f"tool {chosen.name} failed: {exc}")

        messages = [{"role": "system", "content": spec.instructions}]
        if context:
            messages.append({"role": "system", "content": "remembered: " + " / ".join(context)})
        messages.append({"role": "user", "content": task.text})
        if tool_result is not None:
            messages.append({"role": "tool", "content": json.dumps(tool_result, default=str)})
        response = await services.model.complete(messages)
        for k in usage:
            usage[k] += response.usage.get(k, 0)
        step("model.completed", model=response.model, usage=response.usage)

        answer = response.text
        if guardrail:
            verdict = await guardrail.check(answer, "output")
            step("guardrail.output", action=verdict.action, reason=verdict.reason)
            if not verdict.allowed:
                return Result(task.id, None, status="denied", steps=steps, served_by=served,
                              usage=usage, error=verdict.reason)
            if verdict.action == "modify":
                answer = verdict.content
                step("guardrail.modified", stage="output")

        if memory:
            try:
                await memory.remember(MemoryItem(f"{task.text} -> {answer}", scope={"agent": spec.name}))
                step("memory.remember")
            except Exception as exc:  # noqa: BLE001
                step("memory.failed", stage="remember", error=f"{type(exc).__name__}: {str(exc)[:200]}")
        telemetry = services.get("telemetry")
        if telemetry:
            await telemetry.emit("agent.completed", agent=spec.name, task=task.id)
        return Result(task.id, answer, status="ok", steps=steps, usage=usage, served_by=served)


ALL = [FakeAgentRuntime, FakeModel, FakeMemory, FakeDecision, FakeGuardrail,
       FakeAuthorization, FakeEvaluation, FakeTelemetry]
