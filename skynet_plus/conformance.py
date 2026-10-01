"""Conformance: the checks every provider of a capability must pass (SP-040).

    from skynet_plus.conformance import check_provider
    problems = asyncio.run(check_provider(MyMemory, {"url": "..."}))
    assert problems == [], problems

The fakes are the reference implementation and pass every check; a real adapter runs the
same list in its own tests. Each check is one sentence; a failure returns that sentence.
"""
from __future__ import annotations

from typing import Any

from .core.contracts import AgentSpec, Result, Task, Tool
from .core.provider import CAPABILITIES, Health, Manifest, Provider
from .core.runrecord import RecorderHandle
from .spi import DecisionRequest, DecisionResult, EvalResult, MemoryItem, ModelResponse, Question, Verdict

THIRD_PARTY_ROOTS = ("langgraph", "langchain", "litellm", "mem0", "openai", "anthropic",
                     "opentelemetry", "deepeval", "praxis")


def _is_skynet_type(value: Any) -> bool:
    module = type(value).__module__ or ""
    return module.startswith("skynet_plus") or module == "builtins"


def _leaks(value: Any) -> str | None:
    """A provider-specific object on the portable side of the interface."""
    module = type(value).__module__ or ""
    if module.split(".")[0] in THIRD_PARTY_ROOTS:
        return f"returns a {module}.{type(value).__name__}; portable results must be Skynet+ types"
    return None


async def check_provider(cls: type[Provider], config: dict | None = None,
                         services: Any = None) -> list[str]:
    problems: list[str] = []
    m = getattr(cls, "manifest", None)
    if not isinstance(m, Manifest):
        return [f"{cls.__name__} has no Manifest"]
    if m.capability not in CAPABILITIES:
        problems.append(f"capability {m.capability!r} is not in the taxonomy")
    if not m.id or not m.version:
        problems.append("manifest needs an id and a version")
    if not isinstance(m.provides, dict) or not any(m.provides.values()):
        problems.append("manifest declares no feature at all")

    try:
        instance = cls(config or {})
    except Exception as exc:  # noqa: BLE001
        return problems + [f"constructor raised {type(exc).__name__}: {exc}"]
    try:
        await instance.initialize()
        health = await instance.health()
        if not isinstance(health, Health):
            problems.append("health() must return a Health")
        elif not health.ok:
            problems.append(f"health() is not ok: {health.detail}")
    except Exception as exc:  # noqa: BLE001
        return problems + [f"lifecycle raised {type(exc).__name__}: {exc}"]

    checker = _CHECKS.get(m.capability)
    if checker is not None:
        try:
            problems += await checker(instance, m, services)
        except Exception as exc:  # noqa: BLE001
            problems.append(f"{m.capability} check raised {type(exc).__name__}: {exc}")
    try:
        await instance.close()
        await instance.close()          # closing twice must be harmless
    except Exception as exc:  # noqa: BLE001
        problems.append(f"close() raised {type(exc).__name__}: {exc}")
    return problems


async def _model(p: Any, m: Manifest, services: Any) -> list[str]:
    out = []
    r = await p.complete([{"role": "system", "content": "Reply briefly."}, {"role": "user", "content": "ping"}])
    if not isinstance(r, ModelResponse):
        return ["complete() must return a ModelResponse"]
    if not isinstance(r.text, str):
        out.append("ModelResponse.text must be a string")
    if not isinstance(r.usage, dict):
        out.append("ModelResponse.usage must be a dict")
    if m.provides.get("structured"):
        r2 = await p.complete([{"role": "user", "content": "ping"}],
                              schema={"type": "object", "properties": {"answer": {"type": "string"}}})
        if not isinstance(r2.structured, dict):
            out.append("declares structured but complete(schema=...) gives no dict in .structured")
    return out


async def _memory(p: Any, m: Manifest, services: Any) -> list[str]:
    out = []
    mid = await p.remember(MemoryItem("the customer prefers email", scope={"agent": "conformance"}))
    if not isinstance(mid, str):
        out.append("remember() must return a string id")
    hits = await p.recall("how does the customer prefer contact", scope={"agent": "conformance"})
    if not isinstance(hits, list) or not all(isinstance(h, MemoryItem) for h in hits):
        out.append("recall() must return a list of MemoryItem")
    elif m.provides.get("recall") and not hits:
        out.append("declares recall but recalls nothing for a near-identical query")
    other = await p.recall("the customer prefers email", scope={"agent": "someone-else"})
    if any(h.content == "the customer prefers email" for h in other):
        out.append("recall() ignores scope")
    n = await p.forget(scope={"agent": "conformance"})
    if not isinstance(n, int):
        out.append("forget() must return the number removed")
    return out


async def _decision(p: Any, m: Manifest, services: Any) -> list[str]:
    out = []
    questions: dict[str, Question] = {}
    if m.provides.get("choice"):
        questions["dept"] = Question("choice", "Which team?", options={"billing": "money", "tech": "bugs"})
    if m.provides.get("score"):
        questions["urgency"] = Question("score", "How urgent?", levels=("low", "high"))
    if m.provides.get("boolean"):
        questions["angry"] = Question("boolean", "Is the customer angry?")
    if m.provides.get("rank"):
        questions["order"] = Question("rank", "Order the teams", options={"billing": "money", "tech": "bugs"})
    if not questions:
        return ["declares no question type"]
    results = await p.decide(DecisionRequest("conformance", "I was billed twice", questions))
    if not isinstance(results, dict) or set(results) != set(questions):
        return ["decide() must return one DecisionResult per question name"]
    for name, r in results.items():
        if not isinstance(r, DecisionResult):
            out.append(f"{name}: not a DecisionResult")
            continue
        total = sum(r.distribution.values())
        if abs(total - 1.0) > 0.01:
            out.append(f"{name}: distribution sums to {total:.3f}, not 1")
        if not 0.0 <= r.confidence <= 1.0:
            out.append(f"{name}: confidence {r.confidence} outside [0, 1]")
        if not isinstance(r.abstain, bool):
            out.append(f"{name}: abstain must be a bool")
        if r.calibrated and not m.provides.get("calibrated"):
            out.append(f"{name}: result says calibrated but the manifest does not declare it")
    return out


async def _guardrail(p: Any, m: Manifest, services: Any) -> list[str]:
    out = []
    for stage in ("input", "output", "tool"):
        if not m.provides.get(stage):
            continue
        content: Any = {"tool": "x", "args": {"q": "hello"}} if stage == "tool" else "hello"
        v = await p.check(content, stage)
        if not isinstance(v, Verdict):
            out.append(f"check(stage={stage}) must return a Verdict")
        elif v.action not in ("allow", "deny", "modify"):
            out.append(f"check(stage={stage}) returned action {v.action!r}")
        elif v.action == "modify" and v.content is None:
            out.append(f"check(stage={stage}) says modify but gives no content")
    return out


async def _evaluation(p: Any, m: Manifest, services: Any) -> list[str]:
    run = {"run_id": "run-x", "agent": "a", "task_id": "t", "task_input": "hi", "profile": "local",
           "providers": {}, "events": [{"name": "run.input", "at": 0.0, "data": {}}],
           "result": Result("t", "hello").to_dict()}
    r = await p.evaluate(run)
    if not isinstance(r, EvalResult):
        return ["evaluate() must return an EvalResult"]
    if not all(isinstance(v, (int, float)) for v in r.scores.values()):
        return ["EvalResult.scores must be numbers"]
    return []


async def _telemetry(p: Any, m: Manifest, services: Any) -> list[str]:
    out = []
    try:
        with p.span("conformance", {"k": "v"}):
            pass
    except Exception as exc:  # noqa: BLE001
        out.append(f"span() must be a context manager: {exc}")
    if m.provides.get("events"):
        await p.emit("conformance.event", k="v")
    return out


async def _authorization(p: Any, m: Manifest, services: Any) -> list[str]:
    a = await p.authorize("x", {})
    return [] if a.decision in ("allow", "deny", "needs_approval") else [f"decision {a.decision!r}"]


async def _agent_runtime(p: Any, m: Manifest, services: Any) -> list[str]:
    if services is None:
        return ["an agent-runtime check needs `services` with at least a model"]
    events: list[tuple[str, dict]] = []
    handle = RecorderHandle(lambda name, data: events.append((name, data)), "run-conformance")
    echo = Tool.from_function(lambda input: {"echo": input}, name="echo")
    spec = AgentSpec("conformance", "Answer briefly.", tools=(echo,))
    result = await p.run(spec, Task("use echo on this"), services, handle)
    if not isinstance(result, Result):
        return ["run() must return a Result"]
    out = []
    if _leaks(result.output):
        out.append(_leaks(result.output) or "")
    if not events:
        out.append("run() recorded no events")
    if result.status not in ("ok", "denied", "needs_approval", "error"):
        out.append(f"status {result.status!r} is not a Result status")
    if m.provides.get("hitl") and not hasattr(p, "run"):
        out.append("declares hitl without a run()")
    return out


_CHECKS = {"model": _model, "memory": _memory, "decision": _decision, "guardrail": _guardrail,
           "evaluation": _evaluation, "telemetry": _telemetry, "authorization": _authorization,
           "agent-runtime": _agent_runtime}
