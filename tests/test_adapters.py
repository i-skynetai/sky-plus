import asyncio
import importlib.util
import os
import re
import unittest
from types import SimpleNamespace
from unittest import mock

from _path import *  # noqa

from skynet_plus import Agent, Kernel, tool
from skynet_plus.conformance import check_provider
from skynet_plus.core.registry import default_registry
from skynet_plus.spi import MemoryItem


def _have(module: str) -> bool:
    try:
        return importlib.util.find_spec(module) is not None
    except ModuleNotFoundError:          # a dotted name whose parent package is absent
        return False


HAVE = {name: _have(mod) for name, mod in
        (("litellm", "litellm"), ("mem0", "mem0"), ("otel", "opentelemetry.sdk"), ("deepeval", "deepeval"))}


@tool
def lookup_order(input: str) -> dict:
    """find an order"""
    return {"order": "".join(c for c in input if c.isdigit()), "status": "shipped"}


class TheRegistryKnowsEveryAdapter(unittest.TestCase):
    def test_each_adapter_is_loaded_or_skipped_with_its_extra(self):
        reg = default_registry()
        for module, (cap, pid, have) in {"litellm_model": ("model", "litellm", HAVE["litellm"]),
                                         "mem0_memory": ("memory", "mem0", HAVE["mem0"]),
                                         "otel_telemetry": ("telemetry", "opentelemetry", HAVE["otel"]),
                                         "deepeval_evaluation": ("evaluation", "deepeval", HAVE["deepeval"])}.items():
            if have:
                self.assertIsNotNone(reg.get(cap, pid), module)
            else:
                self.assertIn(module, reg.skipped)


@unittest.skipUnless(HAVE["litellm"], "litellm is not installed")
class TheLiteLLMModel(unittest.TestCase):
    def setUp(self):
        from skynet_plus.providers.litellm_model import LiteLLMModel
        self.cls = LiteLLMModel

    def test_health_names_the_missing_key_and_passes_with_one(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("OPENAI_API_KEY", None)
            h = asyncio.run(self.cls({"model": "gpt-4o-mini"}).health())
            self.assertFalse(h.ok); self.assertIn("OPENAI_API_KEY", h.detail)
            os.environ["OPENAI_API_KEY"] = "test-key-not-real"
            self.assertTrue(asyncio.run(self.cls({"model": "gpt-4o-mini"}).health()).ok)

    def test_a_mock_completion_maps_text_usage_cost_and_structured_output(self):
        m = self.cls({"model": "gpt-4o-mini"})
        r = asyncio.run(m.complete([{"role": "user", "content": "hi"}], mock_response="hello there"))
        self.assertEqual(r.text, "hello there")
        self.assertGreater(r.usage["input_tokens"], 0)
        self.assertGreaterEqual(r.usage["cost_usd"], 0.0)
        self.assertEqual(r.tool_calls, [])
        r2 = asyncio.run(m.complete([{"role": "user", "content": "hi"}], schema={"type": "object", "properties": {"action": {}}},
                                    mock_response='{"action": "final", "answer": "ok"}'))
        self.assertEqual(r2.structured, {"action": "final", "answer": "ok"})

    def test_tool_calls_map_to_plain_dicts(self):
        call = SimpleNamespace(id="c1", function=SimpleNamespace(name="lookup_order", arguments='{"input": "4412"}'))
        fake = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=None, tool_calls=[call]))],
                               usage=SimpleNamespace(prompt_tokens=3, completion_tokens=4), model="gpt-4o-mini")
        async def acompletion(**kwargs):
            self.assertEqual(kwargs["tools"][0]["function"]["name"], "lookup_order")
            return fake
        with mock.patch("skynet_plus.providers.litellm_model.litellm.acompletion", acompletion):
            r = asyncio.run(self.cls({"model": "gpt-4o-mini"}).complete([{"role": "user", "content": "x"}], tools=[lookup_order]))
        self.assertEqual(r.tool_calls, [{"id": "c1", "name": "lookup_order", "arguments": {"input": "4412"}}])
        self.assertEqual(r.usage["input_tokens"], 3)

    def test_a_provider_error_is_a_skynet_error(self):
        from skynet_plus import ProviderError
        async def boom(**kwargs):
            raise RuntimeError("upstream down")
        with mock.patch("skynet_plus.providers.litellm_model.litellm.acompletion", boom):
            with self.assertRaises(ProviderError) as cm:
                asyncio.run(self.cls({"model": "gpt-4o-mini"}).complete([{"role": "user", "content": "x"}]))
        self.assertIn("upstream down", str(cm.exception))

    def test_conformance_and_the_reference_agent_on_a_mocked_model(self):
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "test-key-not-real"}):
            self.assertEqual(asyncio.run(check_provider(self.cls, {"model": "gpt-4o-mini", "mock_response": '{"answer": "pong"}'})), [])
            kernel = Kernel.load(None, profile="local", overrides={"model": {"provider": "litellm", "model": "gpt-4o-mini",
                                                                              "mock_response": '{"action": "final", "answer": "all good"}'}})
            result = Agent("a", "Answer briefly.", kernel=kernel).run_sync("hello")
            self.assertTrue(result.ok, result.error)
            self.assertTrue(result.served_by["model"].startswith("litellm@"))


class _StubMem0:
    """What the adapter talks to: Mem0's AsyncMemory shape, in memory."""
    rows: list[dict] = []

    @classmethod
    def from_config(cls, config):
        return cls()

    async def add(self, messages, *, metadata=None, infer=True, **ids):
        row = {"id": f"m{len(self.rows) + 1}", "memory": messages, "metadata": metadata or {}, **ids}
        self.rows.append(row)
        return {"results": [row]}

    async def search(self, query, *, top_k=20, filters=None, threshold=0.1, **kw):
        q = set(re.findall(r"[a-z0-9]+", query.lower()))
        out = []
        for r in self.rows:
            if any(r.get(k) != v for k, v in (filters or {}).items()):
                continue
            t = set(re.findall(r"[a-z0-9]+", r["memory"].lower()))
            score = len(q & t) / max(1, len(q | t))
            if score > 0:
                out.append({**r, "score": round(score, 3)})
        return {"results": sorted(out, key=lambda r: -r["score"])[:top_k]}

    async def get_all(self, *, filters=None, top_k=20, **kw):
        return {"results": [r for r in self.rows if not any(r.get(k) != v for k, v in (filters or {}).items())][:top_k]}

    async def delete_all(self, **ids):
        self.rows[:] = [r for r in self.rows if any(r.get(k) != v for k, v in ids.items())]


@unittest.skipUnless(HAVE["mem0"], "mem0 is not installed")
class TheMem0Memory(unittest.TestCase):
    def setUp(self):
        _StubMem0.rows = []
        self.patch = mock.patch("skynet_plus.providers.mem0_memory.AsyncMemory", _StubMem0)
        self.patch.start()
        from skynet_plus.providers.mem0_memory import Mem0Memory
        self.cls = Mem0Memory

    def tearDown(self):
        self.patch.stop()

    def test_scope_maps_to_mem0_ids_and_recall_respects_it(self):
        m = self.cls({})
        asyncio.run(m.initialize())
        self.assertTrue(asyncio.run(m.health()).ok)
        self.assertEqual(m._ids({"agent": "a1", "user": "u1"}), {"agent_id": "a1", "user_id": "u1"})
        self.assertEqual(m._ids(None), {"agent_id": "skynet"})
        asyncio.run(m.remember(MemoryItem("prefers email", scope={"agent": "a1"})))
        hits = asyncio.run(m.recall("email", scope={"agent": "a1"}))
        self.assertEqual(hits[0].content, "prefers email")
        self.assertEqual(asyncio.run(m.recall("email", scope={"agent": "other"})), [])
        self.assertEqual(asyncio.run(m.forget(scope={"agent": "a1"})), 1)

    def test_conformance(self):
        self.assertEqual(asyncio.run(check_provider(self.cls, {})), [])

    def test_extraction_failure_falls_back_to_raw_storage_and_says_so(self):
        class Rejecting(_StubMem0):
            async def add(self, messages, *, metadata=None, infer=True, **ids):
                if infer:
                    raise RuntimeError("Unsupported value: 'temperature'")
                return await super().add(messages, metadata=metadata, infer=False, **ids)
        with mock.patch("skynet_plus.providers.mem0_memory.AsyncMemory", Rejecting):
            m = self.cls({})
            asyncio.run(m.initialize())
            mid = asyncio.run(m.remember(MemoryItem("prefers email", scope={"agent": "a1"})))
            self.assertTrue(mid)
            self.assertEqual(len(m.warnings), 1)
            self.assertIn("stored the text as written", m.warnings[0])
            self.assertEqual(asyncio.run(m.recall("email", scope={"agent": "a1"}))[0].metadata, {"raw": True})

    def test_defaults_use_a_model_that_accepts_temperature_and_a_project_local_store(self):
        m = self.cls({"__skynet__": {"config_dir": "/proj", "run_log": "/proj/.skynet/runs.jsonl", "profile": "development"}})
        self.assertEqual(m.mem0_config["llm"]["config"]["model"], "gpt-4o-mini")
        self.assertEqual(m.mem0_config["vector_store"]["config"]["path"], "/proj/.skynet/mem0")
        self.assertEqual(self.cls({"llm_model": "gpt-4.1-mini"}).mem0_config["llm"]["config"]["model"], "gpt-4.1-mini")
        self.assertEqual(self.cls({"config": {"llm": {"provider": "ollama"}}}).mem0_config, {"llm": {"provider": "ollama"}})

    def test_a_store_that_cannot_start_is_a_health_failure_not_a_crash(self):
        class Broken:
            @classmethod
            def from_config(cls, config): raise RuntimeError("no OPENAI_API_KEY")
        with mock.patch("skynet_plus.providers.mem0_memory.AsyncMemory", Broken):
            m = self.cls({})
            asyncio.run(m.initialize())
            h = asyncio.run(m.health())
            self.assertFalse(h.ok); self.assertIn("OPENAI_API_KEY", h.detail)


@unittest.skipUnless(HAVE["otel"], "opentelemetry-sdk is not installed")
class TheOpenTelemetryProvider(unittest.TestCase):
    def test_a_run_produces_a_span_per_provider_call_and_per_tool(self):
        kernel = Kernel.load(None, profile="local", overrides={"telemetry": {"provider": "opentelemetry", "exporter": "memory"}})
        async def go():
            async with kernel:
                result = await Agent("t", "x", tools=[lookup_order], kernel=kernel).run("order 4412")
                self.assertTrue(result.ok, result.error)
                return kernel.services.telemetry.finished_spans()
        spans = asyncio.run(go())
        names = [s.name for s in spans]
        for expected in ("agent.run", "model.complete", "memory.recall", "guardrail.check", "tool.lookup_order", "memory.remember"):
            self.assertIn(expected, names, names)
        model_span = next(s for s in spans if s.name == "model.complete")
        self.assertEqual(model_span.attributes["provider"], "fake")
        self.assertEqual(model_span.attributes["version"], "1.0.0")
        run_span = next(s for s in spans if s.name == "agent.run")
        self.assertTrue(all(s.parent is not None for s in spans if s.name != "agent.run"))
        self.assertTrue(any(e.name == "agent.completed" for e in run_span.events) or
                        any(e.name == "agent.completed" for s in spans for e in s.events))

    def test_conformance(self):
        from skynet_plus.providers.otel_telemetry import OpenTelemetryTelemetry
        self.assertEqual(asyncio.run(check_provider(OpenTelemetryTelemetry, {"exporter": "memory"})), [])

    def test_nothing_is_printed_unless_an_exporter_is_chosen(self):
        from skynet_plus.providers.otel_telemetry import OpenTelemetryTelemetry
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("OTEL_EXPORTER_OTLP_ENDPOINT", None)
            self.assertEqual(OpenTelemetryTelemetry({}).exporter_name, "none")
            os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = "http://localhost:4318"
            self.assertEqual(OpenTelemetryTelemetry({}).exporter_name, "otlp")


@unittest.skipUnless(HAVE["deepeval"], "deepeval is not installed")
class TheDeepEvalProvider(unittest.TestCase):
    CONFIG = {"metrics": [{"name": "helpers_deepeval:LengthMetric", "min_chars": 3}]}

    def test_the_run_record_becomes_a_test_case_with_tools(self):
        from skynet_plus.providers.deepeval_evaluation import DeepEvalEvaluation
        kernel = Kernel.load(None, profile="local", overrides={"evaluation": {"provider": "deepeval", **self.CONFIG}})
        async def go():
            async with kernel:
                agent = Agent("e", "x", tools=[lookup_order], kernel=kernel)
                result = await agent.run("order 4412")
                return await agent.evaluate(result), agent.record(result.run_id)
        ev, record = asyncio.run(go())
        self.assertEqual(ev.scores, {"LengthMetric": 1.0})
        self.assertTrue(ev.passed)
        case = DeepEvalEvaluation.test_case(record)
        self.assertEqual(case.input, "order 4412")
        self.assertEqual(case.tools_called[0].name, "lookup_order")

    def test_an_unknown_metric_is_a_health_failure(self):
        from skynet_plus.providers.deepeval_evaluation import DeepEvalEvaluation
        p = DeepEvalEvaluation({"metrics": ["NoSuchMetric"]})
        asyncio.run(p.initialize())
        self.assertFalse(asyncio.run(p.health()).ok)

    def test_conformance(self):
        from skynet_plus.providers.deepeval_evaluation import DeepEvalEvaluation
        self.assertEqual(asyncio.run(check_provider(DeepEvalEvaluation, self.CONFIG)), [])


class TheFakeTelemetrySeesTheSameSpans(unittest.TestCase):
    def test_kernel_tracing_works_with_any_telemetry_provider(self):
        kernel = Kernel.load(None, profile="local")
        async def go():
            async with kernel:
                await Agent("t", "x", tools=[lookup_order], kernel=kernel).run("order 1")
                return [s["name"] for s in kernel.services.telemetry.spans]
        names = asyncio.run(go())
        for expected in ("agent.run", "model.complete", "guardrail.check", "tool.lookup_order"):
            self.assertIn(expected, names, names)


if __name__ == "__main__":
    unittest.main()
