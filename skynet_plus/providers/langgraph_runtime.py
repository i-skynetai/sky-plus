"""LangGraph agent runtime — a fixed, governed graph (SP-022).

    START → guard_input → recall → plan ─┬─ tool ──→ govern ─┬─ allow → act → plan
                                         │                   └─ deny / approval → END
                                         └─ final → finish → END

The application never sees the graph. The model is reached through the Skynet+ model
port, so this runtime works with any configured model provider, including the fake.
"""
from __future__ import annotations

import inspect
import json
import re
from dataclasses import dataclass, field
from importlib import metadata
from typing import Any, TypedDict

from langchain_core.runnables import RunnableConfig   # a LangGraph dependency
from langgraph.graph import END, START, StateGraph

try:
    from langgraph.checkpoint.memory import InMemorySaver
except ImportError:  # LangGraph < 1.0
    from langgraph.checkpoint.memory import MemorySaver as InMemorySaver  # type: ignore[no-redef]

from ..core.contracts import AgentSpec, Result, Step, Task
from ..core.provider import Health, Manifest
from ..core.runrecord import RecorderHandle
from ..spi import AgentRuntimeProvider, MemoryItem

VERSION = "0.2.0"

PROPOSAL_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "action": {"type": "string", "enum": ["tool", "final"]},
        "tool": {"type": "string"},
        "args": {"type": "object"},
        "answer": {"type": "string"},
    },
    "required": ["action"],
}

_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)


class RunState(TypedDict, total=False):
    task: str
    context: list[str]
    proposal: dict | None
    history: list[dict]
    answer: str | None
    status: str            # running | ok | denied | needs_approval | error
    error: str | None
    usage: dict
    turns: int


@dataclass
class _RunContext:
    """Objects a run needs that must not enter graph state (they are not serialisable)."""
    spec: AgentSpec
    task: Task
    services: Any
    recorder: RecorderHandle
    steps: list[Step] = field(default_factory=list)

    def step(self, kind: str, **detail: Any) -> None:
        self.steps.append(Step(kind, detail))
        self.recorder.event(kind, **detail)


def _extract_json(text: str) -> dict | None:
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else None
    except (json.JSONDecodeError, TypeError):
        pass
    m = _JSON_BLOCK.search(text or "")
    if m:
        try:
            data = json.loads(m.group(0))
            return data if isinstance(data, dict) else None
        except json.JSONDecodeError:
            return None
    return None


class LangGraphRuntime(AgentRuntimeProvider):
    manifest = Manifest(
        id="langgraph", capability="agent-runtime", version=VERSION,
        provides={"agents": True, "streaming": False, "checkpointing": True, "hitl": True},
        requires=("model",), package="langgraph",
        description="a fixed, governed graph: guard → recall → plan → govern → act → finish; checkpointed per run",
    )

    def __init__(self, config: dict | None = None) -> None:
        super().__init__(config)
        self.max_turns = int(self.config.get("max_turns", 8))
        self._runs: dict[str, _RunContext] = {}
        self._checkpointer = InMemorySaver()
        self._graph = self._build()

    async def health(self) -> Health:
        try:
            version = metadata.version("langgraph")
        except metadata.PackageNotFoundError:
            version = "unknown"
        return Health(ok=True, detail=f"langgraph {version}; max_turns {self.max_turns}",
                      checks={"langgraph": version})

    async def close(self) -> None:
        self._runs.clear()

    # -- the graph --------------------------------------------------------------------
    def _build(self):
        g = StateGraph(RunState)
        g.add_node("guard_input", self._guard_input)
        g.add_node("recall", self._recall)
        g.add_node("plan", self._plan)
        g.add_node("govern", self._govern)
        g.add_node("act", self._act)
        g.add_node("finish", self._finish)
        g.add_edge(START, "guard_input")
        g.add_conditional_edges("guard_input", lambda s: "recall" if s.get("status") == "running" else END)
        g.add_edge("recall", "plan")
        g.add_conditional_edges(
            "plan", lambda s: "govern" if (s.get("proposal") or {}).get("action") == "tool" else "finish")
        g.add_conditional_edges("govern", lambda s: "act" if s.get("status") == "running" else END)
        g.add_conditional_edges("act", lambda s: "plan" if s.get("status") == "running" else "finish")
        g.add_edge("finish", END)
        return g.compile(checkpointer=self._checkpointer)

    def _ctx(self, config: RunnableConfig) -> _RunContext:
        return self._runs[config["configurable"]["thread_id"]]

    async def _guard_input(self, state: RunState, config: RunnableConfig) -> dict:
        ctx = self._ctx(config)
        ctx.step("run.input", task=ctx.task.text, agent=ctx.spec.name, runtime="langgraph")
        guard = ctx.services.get("guardrail")
        if guard:
            verdict = await guard.check(ctx.task.input, "input")
            ctx.step("guardrail.input", action=verdict.action, reason=verdict.reason)
            if not verdict.allowed:
                return {"status": "denied", "error": verdict.reason}
        return {}

    async def _recall(self, state: RunState, config: RunnableConfig) -> dict:
        ctx = self._ctx(config)
        memory = ctx.services.get("memory")
        if not memory:
            return {"context": []}
        hits = await memory.recall(ctx.task.text, scope={"agent": ctx.spec.name})
        ctx.step("memory.recall", hits=len(hits))
        return {"context": [m.content for m in hits]}

    def _messages(self, ctx: _RunContext, state: RunState) -> list[dict]:
        messages = [{"role": "system", "content": ctx.spec.instructions}]
        if ctx.spec.tools:
            catalogue = [{"name": t.name, "description": t.description, "parameters": t.parameters}
                         for t in ctx.spec.tools]
            messages.append({"role": "system", "content": json.dumps({
                "available_tools": catalogue,
                "reply_format": "JSON: {\"action\": \"tool\", \"tool\": name, \"args\": {...}} "
                                "or {\"action\": \"final\", \"answer\": text}"})})
        if state.get("context"):
            messages.append({"role": "system", "content": "remembered: " + " / ".join(state["context"])})
        messages.append({"role": "user", "content": ctx.task.text})
        for item in state.get("history", []):
            messages.append({"role": "assistant", "content": json.dumps(
                {"action": "tool", "tool": item["tool"], "args": item["args"]}, default=str)})
            messages.append({"role": "tool", "content": json.dumps(item["result"], default=str)})
        return messages

    def _parse_proposal(self, response: Any, spec: AgentSpec) -> dict:
        data = response.structured if isinstance(response.structured, dict) else None
        if not data or "action" not in data:
            data = _extract_json(response.text)
        if not data or data.get("action") not in ("tool", "final"):
            return {"action": "final", "answer": response.text}
        if data["action"] == "tool":
            name = data.get("tool")
            if not name or spec.tool(name) is None:
                return {"action": "error", "error": f"the model proposed an unknown tool {name!r}"}
            args = data.get("args")
            return {"action": "tool", "tool": name, "args": args if isinstance(args, dict) else {}}
        return {"action": "final", "answer": data.get("answer") if data.get("answer") is not None else response.text}

    async def _plan(self, state: RunState, config: RunnableConfig) -> dict:
        ctx = self._ctx(config)
        if state.get("turns", 0) >= self.max_turns:
            ctx.step("run.aborted", reason=f"max_turns {self.max_turns} reached without a final answer")
            return {"status": "error", "proposal": None,
                    "error": f"no final answer after {self.max_turns} turns"}
        response = await ctx.services.model.complete(self._messages(ctx, state), schema=PROPOSAL_SCHEMA)
        usage = dict(state.get("usage") or {})
        for key, value in (response.usage or {}).items():
            usage[key] = usage.get(key, 0) + value
        proposal = self._parse_proposal(response, ctx.spec)
        ctx.step("model.completed", model=response.model, usage=response.usage, action=proposal["action"])
        turns = state.get("turns", 0) + 1
        if proposal["action"] == "tool":
            ctx.step("action.proposed", tool=proposal["tool"], args=proposal["args"])
            return {"proposal": proposal, "usage": usage, "turns": turns}
        if proposal["action"] == "error":
            ctx.step("action.rejected", reason=proposal["error"])
            return {"status": "error", "error": proposal["error"], "proposal": None, "usage": usage, "turns": turns}
        return {"proposal": proposal, "answer": proposal["answer"], "usage": usage, "turns": turns}

    async def _govern(self, state: RunState, config: RunnableConfig) -> dict:
        ctx = self._ctx(config)
        proposal = state["proposal"] or {}
        guard = ctx.services.get("guardrail")
        if guard:
            verdict = await guard.check({"tool": proposal["tool"], "args": proposal["args"]}, "tool")
            ctx.step("guardrail.tool", action=verdict.action, reason=verdict.reason)
            if not verdict.allowed:
                return {"status": "denied", "error": verdict.reason}
        auth = ctx.services.get("authorization")
        if auth:
            decision = await auth.authorize(proposal["tool"], {"agent": ctx.spec.name, "task": ctx.task.id,
                                                              "args": proposal["args"]})
            ctx.step("authorization", action=proposal["tool"], decision=decision.decision, reason=decision.reason)
            if decision.decision == "needs_approval":
                return {"status": "needs_approval", "error": decision.reason}
            if decision.decision == "deny":
                return {"status": "denied", "error": decision.reason}
        return {}

    async def _act(self, state: RunState, config: RunnableConfig) -> dict:
        ctx = self._ctx(config)
        proposal = state["proposal"] or {}
        tool = ctx.spec.tool(proposal["tool"])
        args = dict(proposal.get("args") or {})
        args.setdefault("input", ctx.task.text)
        try:
            result = tool.invoke(task=ctx.task, **args)
            if inspect.isawaitable(result):
                result = await result
        except Exception as exc:  # noqa: BLE001 — a tool failure is a result, not a crash
            ctx.step("tool.failed", tool=tool.name, error=f"{type(exc).__name__}: {exc}")
            return {"status": "error", "error": f"tool {tool.name} failed: {exc}"}
        ctx.step("tool.executed", tool=tool.name, result=result)
        history = list(state.get("history") or [])
        history.append({"tool": tool.name, "args": args, "result": result})
        return {"history": history}

    async def _finish(self, state: RunState, config: RunnableConfig) -> dict:
        ctx = self._ctx(config)
        if state.get("status") != "running":
            return {}
        answer = state.get("answer") or ""
        guard = ctx.services.get("guardrail")
        if guard:
            verdict = await guard.check(answer, "output")
            ctx.step("guardrail.output", action=verdict.action, reason=verdict.reason)
            if not verdict.allowed:
                return {"status": "denied", "error": verdict.reason}
        memory = ctx.services.get("memory")
        if memory:
            await memory.remember(MemoryItem(f"{ctx.task.text} -> {answer}", scope={"agent": ctx.spec.name}))
            ctx.step("memory.remember")
        telemetry = ctx.services.get("telemetry")
        if telemetry:
            await telemetry.emit("agent.completed", agent=ctx.spec.name, task=ctx.task.id, runtime="langgraph")
        return {"status": "ok", "answer": answer}

    # -- the port ---------------------------------------------------------------------
    async def run(self, spec: AgentSpec, task: Task, services: Any, recorder: RecorderHandle) -> Result:
        thread_id = recorder.run_id
        ctx = _RunContext(spec, task, services, recorder)
        self._runs[thread_id] = ctx
        initial: RunState = {"task": task.text, "context": [], "proposal": None, "history": [],
                             "answer": None, "status": "running", "error": None,
                             "usage": {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}, "turns": 0}
        final: dict = {}
        try:
            final = await self._graph.ainvoke(initial, config={"configurable": {"thread_id": thread_id}})
        finally:
            if final.get("status") != "needs_approval":
                self._runs.pop(thread_id, None)       # a paused run keeps its context for resume (SP-025)
        status = final.get("status") or "error"
        if status == "ok":
            output: Any = final.get("answer")
        elif status == "needs_approval":
            output = {"pending": (final.get("proposal") or {}).get("tool")}
        else:
            output = None
        return Result(task.id, output, status=status, steps=ctx.steps, usage=final.get("usage", {}),
                      served_by=services.refs(), error=final.get("error"))

    def paused(self, run_id: str) -> bool:
        """True when a run stopped for approval and its checkpoint is still held."""
        return run_id in self._runs
