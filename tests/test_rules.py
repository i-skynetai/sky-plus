import asyncio
import unittest

from _path import *  # noqa

from skynet_plus import Agent, Kernel, tool
from skynet_plus.core.provider import Manifest
from skynet_plus.core.registry import Registry
from skynet_plus.providers import fake
from skynet_plus.providers.rules import RulesGuardrail
from skynet_plus.spi import GuardrailProvider, Verdict


class TheRulesGuardrail(unittest.TestCase):
    def test_patterns_tools_and_size(self):
        g = RulesGuardrail({"deny_tools": ["wire_money"], "max_chars": 50})
        self.assertEqual(asyncio.run(g.check("hello", "input")).action, "allow")
        self.assertEqual(asyncio.run(g.check("sudo rm  -rf /", "input")).action, "deny")
        self.assertEqual(asyncio.run(g.check({"tool": "wire_money"}, "tool")).action, "deny")
        self.assertEqual(asyncio.run(g.check({"tool": "lookup"}, "tool")).action, "allow")
        self.assertEqual(asyncio.run(g.check("x" * 51, "output")).action, "deny")

    def test_patterns_see_nested_strings_as_written(self):
        g = RulesGuardrail()
        for payload in ("DROP\nTABLE users", "drop\ttable users"):
            self.assertEqual(asyncio.run(g.check(payload, "input")).action, "deny")
            self.assertEqual(asyncio.run(g.check({"tool": "sql", "args": {"q": payload}}, "tool")).action, "deny")
            self.assertEqual(asyncio.run(g.check({"args": [{"nested": [payload]}]}, "tool")).action, "deny")

    def test_it_is_usable_from_a_profile_without_installs(self):
        @tool
        def wire_money(input: str):
            return "sent"
        kernel = Kernel.load(None, profile="local", overrides={"guardrail": {"provider": "rules", "deny_tools": ["wire_money"]}})
        result = Agent("g", "x", tools=[wire_money], kernel=kernel).run_sync("wire_money to account 1")
        self.assertEqual(result.status, "denied")
        self.assertIn("deny list", result.error)


class AModifyVerdictSticks(unittest.TestCase):
    def test_the_reference_runtime_uses_the_modified_content_at_every_stage(self):
        class Redact(GuardrailProvider):
            manifest = Manifest(id="redact", capability="guardrail", version="0",
                                provides={"input": True, "output": True, "tool": True})
            async def check(self, content, stage, context=None):
                if stage == "input":
                    return Verdict("modify", "redacted", content=str(content).replace("4412", "[order]"))
                if stage == "tool":
                    return Verdict("modify", "capped", content={"args": {"input": "capped input"}})
                return Verdict("modify", "signed", content=str(content) + " [checked]")

        @tool
        def echo(input: str):
            return {"got": input}
        reg = Registry(); reg.register_all(fake.ALL); reg.register(Redact)
        kernel = Kernel.load(None, profile="local", overrides={"guardrail": "redact"}, registry=reg)
        result = Agent("m", "x", tools=[echo], kernel=kernel).run_sync("order 4412")
        self.assertTrue(result.ok, result.error)
        kinds = [s.kind for s in result.steps]
        self.assertEqual(kinds.count("guardrail.modified"), 3)
        executed = next(s for s in result.steps if s.kind == "tool.executed")
        self.assertEqual(executed.detail["result"], {"got": "capped input"})
        self.assertTrue(result.output.endswith("[checked]"))
        self.assertNotIn("4412", result.output)


if __name__ == "__main__":
    unittest.main()
