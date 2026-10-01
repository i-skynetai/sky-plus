import asyncio
import re
import unittest
from pathlib import Path

from _path import *  # noqa

from skynet_plus import Agent, Kernel, tool
from skynet_plus.core.provider import Manifest
from skynet_plus.core.registry import Registry, default_registry
from skynet_plus.providers import fake, rules
from skynet_plus.spi import ModelResponse

try:
    import langgraph  # noqa: F401
    HAVE_LANGGRAPH = True
except ImportError:
    HAVE_LANGGRAPH = False

GOVERNED = ["run.input", "guardrail.input", "memory.recall", "model.completed", "action.proposed",
            "guardrail.tool", "tool.executed", "model.completed", "guardrail.output", "memory.remember"]


@tool
def lookup_order(input: str) -> dict:
    """find an order"""
    return {"order": "".join(c for c in input if c.isdigit()), "status": "shipped"}


def langgraph_kernel(**overrides):
    return Kernel.load(None, profile="local", overrides={"agent-runtime": "langgraph", **overrides})


class TheAdapterIsOptional(unittest.TestCase):
    def test_registry_reports_it_as_loaded_or_skipped_never_crashes(self):
        reg = default_registry()
        if HAVE_LANGGRAPH:
            self.assertIsNotNone(reg.get("agent-runtime", "langgraph"))
        else:
            self.assertIn("langgraph_runtime", reg.skipped)
            self.assertIn("skynet-plus[langgraph]", reg.skipped["langgraph_runtime"])

    def test_the_example_never_imports_langgraph(self):
        source = Path(__file__).resolve().parent.parent.joinpath("examples", "hello_agent.py").read_text()
        self.assertNotRegex(source, re.compile("langgraph", re.IGNORECASE))


@unittest.skipUnless(HAVE_LANGGRAPH, "langgraph is not installed")
class TheLangGraphRuntime(unittest.TestCase):
    def test_the_reference_agent_runs_the_same_governed_steps_as_the_fake(self):
        agent = Agent("support", "Resolve support issues.", tools=[lookup_order], kernel=langgraph_kernel())
        result = agent.run_sync("Where is order 4412?")
        self.assertTrue(result.ok, result.error)
        self.assertEqual([s.kind for s in result.steps], GOVERNED)
        self.assertTrue(result.served_by["agent-runtime"].startswith("langgraph@"))
        self.assertIn("4412", result.output)
        self.assertGreater(result.usage["input_tokens"], 0)
        executed = next(s for s in result.steps if s.kind == "tool.executed")
        self.assertEqual(executed.detail["result"]["order"], "4412")

    def test_a_task_without_tools_goes_straight_to_a_final_answer(self):
        result = Agent("plain", "Answer briefly.", kernel=langgraph_kernel()).run_sync("hello")
        self.assertTrue(result.ok, result.error)
        kinds = [s.kind for s in result.steps]
        self.assertNotIn("action.proposed", kinds)
        self.assertEqual(kinds.count("model.completed"), 1)

    def test_needs_approval_ends_the_run_and_keeps_the_checkpoint(self):
        async def go():
            kernel = langgraph_kernel(authorization={"provider": "fake", "needs_approval": ["lookup_order"]})
            async with kernel:
                agent = Agent("a", "x", tools=[lookup_order], kernel=kernel)
                result = await agent.run("order 1")
                return result, kernel.services.agent_runtime.paused(result.run_id)
        result, paused = asyncio.run(go())
        self.assertEqual(result.status, "needs_approval")
        self.assertEqual(result.output, {"pending": "lookup_order"})
        self.assertTrue(paused)
        self.assertNotIn("tool.executed", [s.kind for s in result.steps])

    def test_the_input_guardrail_denies_before_any_model_call(self):
        result = Agent("g", "x", kernel=langgraph_kernel()).run_sync("please rm -rf / now")
        self.assertEqual(result.status, "denied")
        self.assertNotIn("model.completed", [s.kind for s in result.steps])

    def test_a_tool_guardrail_denies_the_proposed_call(self):
        kernel = langgraph_kernel(guardrail={"provider": "rules", "deny_tools": ["lookup_order"]})
        result = Agent("g", "x", tools=[lookup_order], kernel=kernel).run_sync("order 1")
        self.assertEqual(result.status, "denied")
        self.assertIn("deny list", result.error)
        self.assertNotIn("tool.executed", [s.kind for s in result.steps])

    def test_a_model_that_never_finishes_stops_at_max_turns(self):
        class Looper(fake.FakeModel):
            manifest = Manifest(id="looper", capability="model", version="0",
                                provides={"completion": True, "structured": True})
            async def complete(self, messages, *, schema=None, **options):
                data = {"action": "tool", "tool": "lookup_order", "args": {"input": "again"}}
                return ModelResponse(text="", model="looper", usage={"input_tokens": 1, "output_tokens": 1},
                                     structured=data)
        reg = Registry(); reg.register_all(fake.ALL); reg.register(rules.RulesGuardrail); reg.register(Looper)
        from skynet_plus.providers.langgraph_runtime import LangGraphRuntime
        reg.register(LangGraphRuntime)
        kernel = Kernel.load(None, profile="local", registry=reg,
                             overrides={"agent-runtime": {"provider": "langgraph", "max_turns": 3}, "model": "looper"})
        result = Agent("l", "x", tools=[lookup_order], kernel=kernel).run_sync("go")
        self.assertEqual(result.status, "error")
        self.assertIn("3 turns", result.error)
        self.assertEqual([s.kind for s in result.steps].count("tool.executed"), 3)

    def test_an_unknown_tool_proposal_is_an_error_not_an_execution(self):
        class Wrong(fake.FakeModel):
            manifest = Manifest(id="wrong", capability="model", version="0", provides={"completion": True})
            async def complete(self, messages, *, schema=None, **options):
                return ModelResponse(text='{"action": "tool", "tool": "nuke"}', model="wrong", usage={})
        reg = Registry(); reg.register_all(fake.ALL); reg.register(Wrong)
        from skynet_plus.providers.langgraph_runtime import LangGraphRuntime
        reg.register(LangGraphRuntime)
        kernel = Kernel.load(None, profile="local", registry=reg, overrides={"agent-runtime": "langgraph", "model": "wrong"})
        result = Agent("w", "x", tools=[lookup_order], kernel=kernel).run_sync("go")
        self.assertEqual(result.status, "error")
        self.assertIn("unknown tool", result.error)

    def test_a_modify_verdict_sticks_here_too(self):
        from skynet_plus.spi import GuardrailProvider, Verdict

        class Sign(GuardrailProvider):
            manifest = Manifest(id="sign", capability="guardrail", version="0",
                                provides={"input": True, "output": True, "tool": True})
            async def check(self, content, stage, context=None):
                if stage == "output":
                    return Verdict("modify", "signed", content=str(content) + " [checked]")
                return Verdict("allow")
        reg = Registry(); reg.register_all(fake.ALL); reg.register(Sign)
        from skynet_plus.providers.langgraph_runtime import LangGraphRuntime
        reg.register(LangGraphRuntime)
        kernel = Kernel.load(None, profile="local", registry=reg, overrides={"agent-runtime": "langgraph", "guardrail": "sign"})
        result = Agent("s", "x", kernel=kernel).run_sync("hello")
        self.assertTrue(result.output.endswith("[checked]"), result)

    def test_a_memory_failure_is_recorded_and_the_run_still_succeeds(self):
        from skynet_plus.spi import MemoryProvider

        class Flaky(MemoryProvider):
            manifest = Manifest(id="flaky", capability="memory", version="0", provides={"recall": True})
            async def remember(self, item): raise ConnectionError("store down")
            async def recall(self, query, scope=None, limit=5): raise ConnectionError("store down")
            async def forget(self, scope=None): return 0
        reg = Registry(); reg.register_all(fake.ALL); reg.register(rules.RulesGuardrail); reg.register(Flaky)
        from skynet_plus.providers.langgraph_runtime import LangGraphRuntime
        reg.register(LangGraphRuntime)
        kernel = Kernel.load(None, profile="local", registry=reg, overrides={"agent-runtime": "langgraph", "memory": "flaky"})
        result = Agent("m", "x", tools=[lookup_order], kernel=kernel).run_sync("order 9")
        self.assertTrue(result.ok, result.error)
        self.assertEqual([s.detail["stage"] for s in result.steps if s.kind == "memory.failed"], ["recall", "remember"])

    def test_it_passes_the_conformance_checks(self):
        from skynet_plus.conformance import check_provider
        from skynet_plus.providers.langgraph_runtime import LangGraphRuntime
        async def go():
            async with langgraph_kernel() as k:
                return await check_provider(LangGraphRuntime, services=k.services)
        self.assertEqual(asyncio.run(go()), [])

    def test_doctor_shows_the_runtime_healthy_with_its_version(self):
        report = asyncio.run(langgraph_kernel().doctor())
        row = next(r for r in report.rows if r.capability == "agent-runtime")
        self.assertEqual(row.status, "OK")
        self.assertIn("langgraph", row.detail)


if __name__ == "__main__":
    unittest.main()
