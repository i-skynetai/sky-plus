import asyncio
import json
import tempfile
import unittest
from pathlib import Path

from _path import *  # noqa

from skynet_plus import Agent, ConfigError, Kernel, ResolutionError, tool
from skynet_plus.core.runrecord import find_run, read_runs
from skynet_plus.spi import DecisionRequest, Question


@tool
def lookup_order(input: str) -> dict:
    """find an order"""
    return {"order": "".join(c for c in input if c.isdigit()), "status": "shipped"}


def config_in(tmp: str, **overrides):
    p = Path(tmp) / "skynet.yaml"
    body = "profile: local\nrun_log: runs.jsonl\n"
    for cap, section in overrides.items():
        body += f"{cap}:\n" + "".join(f"  {k}: {json.dumps(v)}\n" for k, v in section.items())
    p.write_text(body)
    return p


class AnAgentRunsOnTheLocalProfile(unittest.TestCase):
    def test_a_tool_is_proposed_governed_executed_and_recorded(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = config_in(d)
            agent = Agent("support", "Resolve support issues.", tools=[lookup_order], config=cfg)
            result = agent.run_sync("Where is order 4412?")
            self.assertTrue(result.ok, result.error)
            kinds = [s.kind for s in result.steps]
            self.assertEqual(kinds[:2], ["run.input", "guardrail.input"])
            for kind in ("action.proposed", "tool.executed", "model.completed"):
                self.assertIn(kind, kinds)
            self.assertIn("4412", json.dumps(result.to_dict()))
            self.assertEqual(result.served_by["model"], "fake@1.0.0")
            log = Path(d).resolve() / "runs.jsonl"            # next to the config file
            runs = read_runs(log)
            self.assertEqual(len(runs), 1)
            self.assertEqual(runs[0]["run_id"], result.run_id)
            self.assertEqual(runs[0]["result"]["status"], "ok")
            self.assertTrue(any(e["name"] == "tool.executed" for e in runs[0]["events"]))
            self.assertEqual(find_run(log)["run_id"], result.run_id)

    def test_providers_stay_up_between_plain_runs_until_closed(self):
        async def go():
            agent = Agent("m", "Remember things.", profile="local")
            await agent.run("the customer prefers email")
            second = await agent.run("how does the customer prefer contact")
            kernel = agent.kernel()
            self.assertTrue(kernel.services.has("memory"))
            await agent.close(); await agent.close()              # twice is harmless
            self.assertFalse(kernel.services.has("memory"))
            return second
        second = asyncio.run(go())
        recall = next(s for s in second.steps if s.kind == "memory.recall")
        self.assertGreaterEqual(recall.detail["hits"], 1)

    def test_run_sync_closes_what_it_started(self):
        agent = Agent("s", "x", profile="local")
        self.assertTrue(agent.run_sync("hi").ok)
        self.assertFalse(agent.kernel().services.has("model"))

    def test_the_guardrail_denies_and_the_run_is_still_recorded(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = config_in(d)
            result = Agent("g", "x", config=cfg).run_sync("please rm -rf / now")
            self.assertEqual(result.status, "denied")
            self.assertIn("rm", result.error)
            self.assertEqual(read_runs(Path(d).resolve() / "runs.jsonl")[0]["result"]["status"], "denied")

    def test_authorization_can_ask_for_a_human(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = config_in(d, authorization={"provider": "fake", "needs_approval": ["lookup_order"]})
            result = Agent("a", "x", tools=[lookup_order], config=cfg).run_sync("order 1")
            self.assertEqual(result.status, "needs_approval")
            self.assertEqual(result.output, {"pending": "lookup_order"})

    def test_a_failing_tool_is_an_error_result_not_an_exception(self):
        @tool
        def broken(input: str):
            raise ValueError("nope")
        result = Agent("b", "x", tools=[broken], profile="local").run_sync("go")
        self.assertEqual(result.status, "error")
        self.assertIn("nope", result.error)

    def test_requirements_are_checked_before_the_run_and_misspellings_are_config_errors(self):
        agent = Agent("r", "x", requirements={"streaming": True}, profile="local")
        with self.assertRaises(ResolutionError):
            agent.run_sync("go")
        with self.assertRaises(ConfigError):
            Agent("r", "x", requirements={"streamng": True}, profile="local")

    def test_evaluate_receives_the_whole_run_record(self):
        seen = {}

        class Spy(__import__("skynet_plus.providers.fake", fromlist=["FakeEvaluation"]).FakeEvaluation):
            async def evaluate(self, run, metrics=None):
                seen.update(run)
                return await super().evaluate(run, metrics)
        from skynet_plus.core.provider import Manifest
        from skynet_plus.core.registry import Registry
        from skynet_plus.providers import fake
        Spy.manifest = Manifest(id="spy", capability="evaluation", version="0", provides={"outcome": True})
        reg = Registry(); reg.register_all(fake.ALL); reg.register(Spy)
        kernel = Kernel.load(None, profile="local", overrides={"evaluation": "spy"}, registry=reg)
        async def go():
            async with kernel:
                agent = Agent("e", "x", tools=[lookup_order], kernel=kernel)
                result = await agent.run("order 7")
                return await agent.evaluate(result)
        scores = asyncio.run(go()).scores
        self.assertEqual(scores["completed"], 1.0)
        for key in ("run_id", "task_input", "events", "providers", "result"):
            self.assertIn(key, seen)
        self.assertIn("tool.executed", [e["name"] for e in seen["events"]])


class MemoryIsAuxiliary(unittest.TestCase):
    def test_a_memory_that_fails_is_recorded_and_the_run_still_succeeds(self):
        from skynet_plus.core.provider import Manifest
        from skynet_plus.core.registry import Registry
        from skynet_plus.providers import fake
        from skynet_plus.spi import MemoryProvider

        class Flaky(MemoryProvider):
            manifest = Manifest(id="flaky", capability="memory", version="0", provides={"recall": True})
            async def remember(self, item): raise ConnectionError("store down")
            async def recall(self, query, scope=None, limit=5): raise ConnectionError("store down")
            async def forget(self, scope=None): return 0
        reg = Registry(); reg.register_all(fake.ALL); reg.register(Flaky)
        kernel = Kernel.load(None, profile="local", overrides={"memory": "flaky"}, registry=reg)
        result = Agent("m", "x", tools=[lookup_order], kernel=kernel).run_sync("order 9")
        self.assertTrue(result.ok, result.error)
        failed = [s for s in result.steps if s.kind == "memory.failed"]
        self.assertEqual([s.detail["stage"] for s in failed], ["recall", "remember"])
        self.assertIn("store down", failed[0].detail["error"])

    def test_providers_receive_the_project_context(self):
        from skynet_plus.core.provider import Manifest
        from skynet_plus.core.registry import Registry
        from skynet_plus.providers import fake
        seen = {}

        class Nosy(fake.FakeModel):
            manifest = Manifest(id="nosy", capability="model", version="0", provides={"completion": True})
            def __init__(self, config=None):
                super().__init__(config); seen.update(self.config.get("__skynet__", {}))
        reg = Registry(); reg.register_all(fake.ALL); reg.register(Nosy)
        with tempfile.TemporaryDirectory() as d:
            cfg = config_in(d)
            Agent("p", "x", config=cfg, kernel=Kernel.load(cfg, registry=reg, overrides={"model": "nosy"})).run_sync("hi")
            self.assertEqual(seen["config_dir"], str(Path(d).resolve()))
            self.assertEqual(seen["profile"], "local")


class TheDecisionServiceAbstainsWhenUnsure(unittest.TestCase):
    def test_choice_boolean_score_and_rank(self):
        async def go():
            async with Kernel.load(None, profile="local") as k:
                req = DecisionRequest("support.triage", "I was billed twice, please refund the duplicate invoice", {
                    "department": Question("choice", "Who handles this?",
                                           options={"billing": "invoices, payments, refunds",
                                                    "technical": "bugs, outages", "sales": "quotes"}),
                    "urgency": Question("score", "How urgent?", levels=("low", "medium", "critical")),
                    "churn": Question("noul", "Does the customer threaten to cancel?"),
                    "order": Question("rank", "Order the teams", options={"billing": "money", "sales": "deals"}),
                })
                return await k.services.decision.decide(req)
        out = asyncio.run(go())
        self.assertEqual(out["department"].answer, "billing")
        self.assertFalse(out["department"].abstain)
        self.assertAlmostEqual(sum(out["department"].distribution.values()), 1.0, places=3)
        self.assertIn(out["urgency"].answer, ("low", "medium", "critical"))
        self.assertIsInstance(out["churn"].answer, bool)
        self.assertEqual(out["order"].answer[0], "billing")
        self.assertTrue(out["urgency"].abstain)


if __name__ == "__main__":
    unittest.main()
