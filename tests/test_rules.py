import asyncio, unittest
from _path import *  # noqa
from skynet_plus import Agent, tool
from skynet_plus.providers.rules import RulesGuardrail


class TheRulesGuardrail(unittest.TestCase):
    def test_patterns_tools_and_size(self):
        g = RulesGuardrail({"deny_tools": ["wire_money"], "max_chars": 50})
        self.assertEqual(asyncio.run(g.check("hello", "input")).action, "allow")
        self.assertEqual(asyncio.run(g.check("sudo rm  -rf /", "input")).action, "deny")
        self.assertEqual(asyncio.run(g.check({"tool": "wire_money"}, "tool")).action, "deny")
        self.assertEqual(asyncio.run(g.check({"tool": "lookup"}, "tool")).action, "allow")
        self.assertEqual(asyncio.run(g.check("x" * 51, "output")).action, "deny")

    def test_it_is_usable_from_a_profile_without_installs(self):
        @tool
        def wire_money(input: str):
            return "sent"
        agent = Agent("g", "x", tools=[wire_money], profile="local")
        agent.kernel().config.capabilities["guardrail"] = {"provider": "rules", "deny_tools": ["wire_money"]}
        result = asyncio.run(agent.run("wire_money to account 1"))
        self.assertEqual(result.status, "denied")
        self.assertIn("deny list", result.error)


if __name__ == "__main__":
    unittest.main()
