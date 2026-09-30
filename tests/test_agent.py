import asyncio, json, tempfile, unittest
from pathlib import Path
from _path import *  # noqa
from skynet_plus import Agent, Kernel, ResolutionError, tool
from skynet_plus.core.runrecord import find_run, read_runs
from skynet_plus.spi import DecisionRequest, Question


@tool
def lookup_order(input: str) -> dict:
    """find an order"""
    return {"order": "".join(c for c in input if c.isdigit()), "status": "shipped"}


def kernel_in(tmp: str, **overrides):
    p = Path(tmp) / "skynet.yaml"
    body = "profile: local\nrun_log: " + str(Path(tmp) / "runs.jsonl") + "\n"
    for cap, section in overrides.items():
        body += f"{cap}:\n" + "".join(f"  {k}: {json.dumps(v)}\n" for k, v in section.items())
    p.write_text(body)
    return p


class AnAgentRunsOnTheLocalProfile(unittest.TestCase):
    def test_a_tool_is_proposed_governed_executed_and_recorded(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = kernel_in(d)
            agent = Agent("support", "Resolve support issues.", tools=[lookup_order], config=cfg)
            result = asyncio.run(agent.run("Where is order 4412?"))
            self.assertTrue(result.ok, result.error)
            kinds = [s.kind for s in result.steps]
            self.assertEqual(kinds[:2], ["run.input", "guardrail.input"])
            self.assertIn("action.proposed", kinds)
            self.assertIn("tool.executed", kinds)
            self.assertIn("model.completed", kinds)
            self.assertIn("4412", json.dumps(result.to_dict()))
            self.assertEqual(result.served_by["model"], "fake@0.1.0")
            runs = read_runs(Path(d) / "runs.jsonl")
            self.assertEqual(len(runs), 1)
            self.assertEqual(runs[0]["run_id"], result.run_id)
            self.assertEqual(runs[0]["result"]["status"], "ok")
            self.assertTrue(any(e["kind"] == "tool.executed" for e in runs[0]["events"]))
            self.assertEqual(find_run(Path(d) / "runs.jsonl")["run_id"], result.run_id)

    def test_memory_carries_across_runs_when_the_kernel_is_kept(self):
        async def go():
            async with Agent("m", "Remember things.", profile="local") as agent:
                await agent.run("the customer prefers email")
                second = await agent.run("how does the customer prefer contact")
                return second
        second = asyncio.run(go())
        recall = next(s for s in second.steps if s.kind == "memory.recall")
        self.assertGreaterEqual(recall.detail["hits"], 1)

    def test_the_guardrail_denies_and_the_run_is_still_recorded(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = kernel_in(d)
            result = asyncio.run(Agent("g", "x", config=cfg).run("please rm -rf / now"))
            self.assertEqual(result.status, "denied")
            self.assertIn("rm -rf", result.error)
            self.assertEqual(read_runs(Path(d) / "runs.jsonl")[0]["result"]["status"], "denied")

    def test_authorization_can_ask_for_a_human(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = kernel_in(d, authorization={"provider": "fake", "needs_approval": ["lookup_order"]})
            result = asyncio.run(Agent("a", "x", tools=[lookup_order], config=cfg).run("order 1"))
            self.assertEqual(result.status, "needs_approval")
            self.assertEqual(result.output, {"pending": "lookup_order"})

    def test_a_failing_tool_is_an_error_result_not_an_exception(self):
        @tool
        def broken(input: str):
            raise ValueError("nope")
        result = asyncio.run(Agent("b", "x", tools=[broken], profile="local").run("go"))
        self.assertEqual(result.status, "error")
        self.assertIn("nope", result.error)

    def test_requirements_are_checked_before_the_run(self):
        agent = Agent("r", "x", requirements={"streaming": True}, profile="local")
        with self.assertRaises(ResolutionError):
            asyncio.run(agent.run("go"))

    def test_evaluate_scores_the_last_run(self):
        agent = Agent("e", "x", profile="local")
        asyncio.run(agent.run("go"))
        scores = asyncio.run(agent.evaluate()).scores
        self.assertEqual(scores["completed"], 1.0)

    def test_run_sync_works(self):
        self.assertTrue(Agent("s", "x", profile="local").run_sync("hi").ok)


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
        self.assertTrue(out["urgency"].abstain)   # nothing in the state says how urgent it is


if __name__ == "__main__":
    unittest.main()
