"""`Agent`: the one class an application needs."""
from __future__ import annotations

import asyncio
from contextlib import nullcontext
from pathlib import Path
from typing import Any, Callable, Iterable

from ..core.contracts import AgentSpec, Result, Task, Tool, normalise_requirements
from ..core.errors import ProviderError
from ..core.kernel import DoctorReport, Kernel
from ..spi.evaluation import EvalResult


class Agent:
    """
    agent = Agent(name="support-agent", instructions="Resolve support issues.", tools=[crm])
    result = await agent.run("Investigate this payment issue.")

    Which runtime, model, memory, decision engine, guardrails, evaluation and telemetry sit
    underneath is decided by `skynet.yaml` (or the `profile` argument), never by this code.
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

    # -- kernel management --------------------------------------------------------------
    def kernel(self) -> Kernel:
        if self._kernel is None:
            self._kernel = Kernel.load(self._config, profile=self._profile,
                                       requirements=self.spec.requirements)
        return self._kernel

    async def start(self) -> "Agent":
        await self.kernel().start(self.spec.requirements)
        return self

    async def stop(self) -> None:
        if self._kernel is not None and self._owns_kernel:
            await self._kernel.stop()

    async def __aenter__(self) -> "Agent":
        return await self.start()

    async def __aexit__(self, *exc: Any) -> None:
        await self.stop()

    async def doctor(self) -> DoctorReport:
        return await self.kernel().doctor(self.spec.requirements)

    # -- running ----------------------------------------------------------------------
    async def run(self, task: Task | str | dict) -> Result:
        task = Task.of(task)
        kernel = self.kernel()
        started_here = not kernel._started
        if started_here:
            await kernel.start(self.spec.requirements)
        try:
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
            kernel.events.emit("run.finished", run_id=result.run_id, status=result.status)
            self.last_result = result
            return result
        finally:
            if started_here and self._owns_kernel:
                await kernel.stop()

    def run_sync(self, task: Task | str | dict) -> Result:
        return asyncio.run(self.run(task))

    async def evaluate(self, result: Result | None = None, metrics: list[str] | None = None) -> EvalResult:
        """Score a run with the configured evaluation provider, from the run record."""
        result = result or self.last_result
        if result is None:
            raise ValueError("nothing to evaluate: run the agent first")
        kernel = self.kernel()
        started_here = not kernel._started
        if started_here:
            await kernel.start(self.spec.requirements)
        try:
            evaluator = kernel.services.get("evaluation")
            if evaluator is None:
                raise ProviderError("no evaluation provider configured")
            return await evaluator.evaluate({"run_id": result.run_id, "result": result.to_dict()}, metrics)
        finally:
            if started_here and self._owns_kernel:
                await kernel.stop()
