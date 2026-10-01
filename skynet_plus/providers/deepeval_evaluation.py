"""DeepEval evaluation provider (SP-034).

Reads the canonical run record — never a framework trace — into a DeepEval test case:
the task input, the final output, and the tools the run called. Metrics are named in
config: a DeepEval metric class name (`AnswerRelevancyMetric`), or `module:Class` for a
custom `BaseMetric`, each with optional keyword arguments.
"""
from __future__ import annotations

import importlib
import os
from typing import Any

os.environ.setdefault("DEEPEVAL_TELEMETRY_OPT_OUT", "YES")
from deepeval.metrics import BaseMetric  # noqa: E402
from deepeval.test_case import LLMTestCase, ToolCall  # noqa: E402

from ..core.provider import Health, Manifest  # noqa: E402
from ..spi import EvalResult, EvaluationProvider  # noqa: E402

VERSION = "0.2.0"


def _resolve(spec: str | dict) -> tuple[type, dict]:
    name, kwargs = (spec, {}) if isinstance(spec, str) else (str(spec.get("name") or spec.get("metric")), {k: v for k, v in spec.items() if k not in ("name", "metric")})
    if ":" in name:
        module, _, attr = name.partition(":")
        cls = getattr(importlib.import_module(module), attr)
    else:
        cls = getattr(importlib.import_module("deepeval.metrics"), name)
    if not (isinstance(cls, type) and issubclass(cls, BaseMetric)):
        raise TypeError(f"{name} is not a DeepEval BaseMetric")
    return cls, kwargs


class DeepEvalEvaluation(EvaluationProvider):
    manifest = Manifest(id="deepeval", capability="evaluation", version=VERSION,
                        provides={"outcome": True, "trajectory": True, "judge": True}, package="deepeval",
                        description="DeepEval metrics over the canonical run record")

    def __init__(self, config: dict | None = None) -> None:
        super().__init__(config)
        self.specs: list = list(self.config.get("metrics") or ["AnswerRelevancyMetric"])
        self.judge: str | None = self.config.get("model")
        self._metrics: list[tuple[str, type, dict]] = []
        self._error: str | None = None

    async def initialize(self) -> None:
        try:
            for spec in self.specs:
                cls, kwargs = _resolve(spec)
                if self.judge and "model" not in kwargs:
                    kwargs["model"] = self.judge
                self._metrics.append((cls.__name__, cls, kwargs))
        except Exception as exc:  # noqa: BLE001
            self._error = f"{type(exc).__name__}: {exc}"

    async def health(self) -> Health:
        if self._error:
            return Health(ok=False, detail=f"metrics could not be resolved: {self._error}")
        if not self._metrics:
            return Health(ok=False, detail="no metrics configured")
        return Health(ok=True, detail="metrics: " + ", ".join(n for n, _, _ in self._metrics))

    @staticmethod
    def test_case(run: dict) -> LLMTestCase:
        result = run.get("result") or {}
        output = result.get("output")
        tools = [ToolCall(name=str(e["data"].get("tool")), input_parameters=e["data"].get("args") or {},
                          output=e["data"].get("result"))
                 for e in run.get("events", []) if e.get("name") == "tool.executed" and isinstance(e.get("data"), dict)]
        return LLMTestCase(input=str(run.get("task_input") if run.get("task_input") is not None else ""),
                           actual_output=output if isinstance(output, str) else ("" if output is None else str(output)),
                           tools_called=tools or None,
                           metadata={"run_id": run.get("run_id"), "status": result.get("status")})

    async def evaluate(self, run: dict, metrics: list[str] | None = None) -> EvalResult:
        case = self.test_case(run)
        scores: dict[str, float] = {}
        detail: dict[str, Any] = {}
        passed = True
        for name, cls, kwargs in self._metrics:
            if metrics and name not in metrics and name.removesuffix("Metric") not in metrics:
                continue
            metric = cls(**kwargs)
            try:
                await metric.a_measure(case)
                ok = bool(metric.is_successful())
            except Exception as exc:  # noqa: BLE001 — a judge that cannot run is a reported failure
                ok = False
                detail[name] = {"error": f"{type(exc).__name__}: {str(exc)[:200]}"}
                scores[name] = 0.0
                passed = False
                continue
            scores[name] = float(metric.score or 0.0)
            detail[name] = {"reason": getattr(metric, "reason", None), "threshold": getattr(metric, "threshold", None)}
            passed = passed and ok
        return EvalResult(scores=scores, passed=passed, detail=detail)
