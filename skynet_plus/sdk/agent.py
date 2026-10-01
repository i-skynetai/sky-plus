"""`Agent`: the one class an application needs."""
from __future__ import annotations

import asyncio
from contextlib import nullcontext
from pathlib import Path
from typing import Any, Callable, Iterable

from ..core.contracts import AgentSpec, Result, Task, Tool, normalise_requirements
from ..core.errors import ProviderError
from ..core.kernel import DoctorReport, Kernel
from ..core.runrecord import find_run
from ..spi.evaluation import EvalResult


class Agent:
    """
    agent = Agent(name="support-agent", instructions="Resolve support issues.", tools=[crm])
    result = await agent.run("Investigate this payment issue.")
    await agent.close()            # or: async with Agent(...) as agent: ...

    Which runtime, model, memory, decision engine, guardrails, evaluation and telemetry sit
    underneath is decided by `skynet.yaml` (or the `profile` argument), never by this code.
    Providers start on the first run and stay up until `close()`, so memory and connections
    carry across runs.
    """

    def __init__(self, name: str, instructions: str, tools: Iterable[Tool | Callable[..., Any]] = (),
                 requirements: dict | None = None, *, config: str | Path | None = None,
                 profile: str | None = None, kernel: Kernel | None = None,
                 metadata: dict | None = None) -> None:
        self.spec = AgentSpec(name=name, instructions=instructions,
                              tools=tuple(Tool.from_function(t) for t in tools),
                              requirements=normalise_requirements(requirements),
                              metadata=dict(metadata or {}))
        self._config, self._profile = config, profile
        self._kernel = kernel
        self._owns_kernel = kernel is None
        self.last_result: Result | None = None
        self._records: dict[str, dict] = {}

    # -- kernel management --------------------------------------------------------------
    def kernel(self) -> Kernel:
        if self._kernel is None:
            self._kernel = Kernel.load(self._config, profile=self._profile,
                                       requirements=self.spec.requirements)
        return self._kernel

    async def start(self) -> "Agent":
        await self.kernel().start(self.spec.requirements)
        return self

    async def close(self) -> None:
        """Stop the providers this agent started. Safe to call twice."""
        if self._kernel is not None and self._owns_kernel:
            await self._kernel.stop()

    async def __aenter__(self) -> "Agent":
        return await self.start()

    async def __aexit__(self, *exc: Any) -> None:
        await self.close()

    async def doctor(self) -> DoctorReport:
        return await self.kernel().doctor(self.spec.requirements)

    # -- running ----------------------------------------------------------------------
    async def run(self, task: Task | str | dict) -> Result:
        task = Task.of(task)
        kernel = self.kernel()
        await kernel.start(self.spec.requirements)     # a no-op when already up, re-checked
        runtime = kernel.services.get("agent-runtime")
        if runtime is None:
            raise ProviderError("no agent-runtime provider configured")
        recorder = kernel.recorder(self.spec.name, task)
        telemetry = kernel.services.get("telemetry")
        span = telemetry.span("agent.run", {"agent": self.spec.name, "task": task.id,
                                            "run": recorder.record.run_id}) if telemetry else nullcontext()
        kernel.events.emit("run.started", run_id=recorder.record.run_id, agent=self.spec.name)
        with span:
            try:
                result = await runtime.run(self.spec, task, kernel.services, recorder.handle)
            except Exception as exc:  # noqa: BLE001 — the record must still be written
                result = Result(task.id, None, status="error", served_by=kernel.services.refs(),
                                error=f"{type(exc).__name__}: {exc}")
        result.run_id = recorder.record.run_id
        recorder.finish(result)
        self._records[result.run_id] = recorder.record.to_dict()
        kernel.events.emit("run.finished", run_id=result.run_id, status=result.status)
        self.last_result = result
        return result

    def run_sync(self, task: Task | str | dict) -> Result:
        """One run on a fresh event loop. Providers started here are closed here too."""
        async def go() -> Result:
            started_here = self._kernel is None or not self._kernel._started
            try:
                return await self.run(task)
            finally:
                if started_here:
                    await self.close()
        return asyncio.run(go())

    # -- evaluating -------------------------------------------------------------------
    def record(self, run_id: str) -> dict | None:
        """The full run record: from the run log as written, else the in-memory copy."""
        kernel = self.kernel()
        if kernel.config.run_log:
            found = find_run(Path(kernel.config.run_log), run_id)
            if found:
                return found
        return self._records.get(run_id)

    async def evaluate(self, result: Result | None = None, metrics: list[str] | None = None) -> EvalResult:
        """Score a run with the configured evaluation provider, from the whole run record."""
        result = result or self.last_result
        if result is None:
            raise ValueError("nothing to evaluate: run the agent first")
        kernel = self.kernel()
        await kernel.start(self.spec.requirements)
        evaluator = kernel.services.get("evaluation")
        if evaluator is None:
            raise ProviderError("no evaluation provider configured")
        record = (self.record(result.run_id) if result.run_id else None) or {
            "run_id": result.run_id, "agent": self.spec.name, "task_id": result.task_id,
            "task_input": None, "events": [], "result": result.to_dict()}
        return await evaluator.evaluate(record, metrics)
