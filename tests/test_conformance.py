import asyncio
import unittest

from _path import *  # noqa

from skynet_plus import Kernel
from skynet_plus.conformance import check_provider
from skynet_plus.core.provider import Manifest
from skynet_plus.providers import fake, rules
from skynet_plus.spi import MemoryProvider


class EveryBuiltInProviderConforms(unittest.TestCase):
    def test_fakes_and_rules(self):
        for cls in fake.ALL + [rules.RulesGuardrail]:
            if cls.manifest.capability == "agent-runtime":
                continue
            self.assertEqual(asyncio.run(check_provider(cls)), [], cls.__name__)

    def test_the_fake_runtime_with_services(self):
        async def go():
            async with Kernel.load(None, profile="local") as k:
                return await check_provider(fake.FakeAgentRuntime, services=k.services)
        self.assertEqual(asyncio.run(go()), [])

    def test_a_broken_provider_is_named_not_raised(self):
        class Forgetful(MemoryProvider):
            manifest = Manifest(id="forgetful", capability="memory", version="0", provides={"recall": True})
            async def remember(self, item): return "id"
            async def recall(self, query, scope=None, limit=5): return []
            async def forget(self, scope=None): return 0
        problems = asyncio.run(check_provider(Forgetful))
        self.assertTrue(any("recalls nothing" in p for p in problems), problems)

    def test_a_manifest_that_promises_nothing_is_a_problem(self):
        class Empty(MemoryProvider):
            manifest = Manifest(id="empty", capability="memory", version="0")
        self.assertTrue(any("no feature" in p for p in asyncio.run(check_provider(Empty))))


if __name__ == "__main__":
    unittest.main()
