import asyncio, tempfile, unittest
from pathlib import Path
from _path import *  # noqa
from skynet_plus import Kernel, ResolutionError, ProviderError
from skynet_plus.core.provider import Health, Manifest
from skynet_plus.core.registry import Registry
from skynet_plus.providers import fake
from skynet_plus.spi import ModelProvider


class TheKernelStartsAndStops(unittest.TestCase):
    def test_local_profile_starts_every_provider_and_records_the_order(self):
        async def go():
            async with Kernel.load(None, profile="local") as k:
                self.assertTrue(k.services.has("agent-runtime"))
                self.assertEqual(k.services.model.manifest.id, "fake")
                self.assertEqual(sorted(k.services.refs()), sorted(k.config.capabilities))
                return [d["capability"] for kind, d in k.events.history if kind == "provider.started"]
        order = asyncio.run(go())
        self.assertLess(order.index("model"), order.index("agent-runtime"))

    def test_start_refuses_an_unsatisfied_requirement_before_initialising(self):
        k = Kernel.load(None, profile="local")
        with self.assertRaises(ResolutionError) as cm:
            asyncio.run(k.start({"agent-runtime": {"streaming": True}}))
        self.assertIn("streaming", str(cm.exception))
        self.assertFalse(k.services.has("model"))

    def test_an_unhealthy_provider_stops_the_start_and_closes_the_rest(self):
        closed = []

        class Sick(fake.FakeTelemetry):          # telemetry starts last in the local profile
            manifest = Manifest(id="sick", capability="telemetry", version="0")
            async def health(self):
                return Health(ok=False, detail="no pulse")

        class Watch(fake.FakeModel):             # model starts first; its close must be called
            manifest = Manifest(id="watch", capability="model", version="0")
            async def close(self):
                closed.append("model")

        reg = Registry(); reg.register_all(fake.ALL); reg.register(Sick); reg.register(Watch)
        k = Kernel.load(None, profile="local", overrides={"model": "watch", "telemetry": "sick"}, registry=reg)
        with self.assertRaises(ProviderError) as cm:
            asyncio.run(k.start())
        self.assertIn("no pulse", str(cm.exception))
        self.assertIn("model", closed)
        self.assertFalse(k.services.has("model"))


class DoctorReports(unittest.TestCase):
    def test_local_is_ok_and_unconfigured_rows_are_informational(self):
        report = asyncio.run(Kernel.load(None, profile="local").doctor())
        self.assertTrue(report.ok, report.render())
        by = {r.capability: r for r in report.rows}
        self.assertEqual(by["model"].status, "OK")
        self.assertEqual(by["payment"].status, "UNCONFIGURED")
        self.assertIn("verdict: OK", report.render())

    def test_development_without_extras_lists_every_missing_provider(self):
        report = asyncio.run(Kernel.load(None, profile="development").doctor())
        self.assertFalse(report.ok)
        missing = {r.capability: r for r in report.rows if r.status == "MISSING"}
        self.assertIn("agent-runtime", missing)
        self.assertIn('skynet-plus[langgraph]', missing["agent-runtime"].detail)
        self.assertIn("NOT READY", report.render())

    def test_doctor_never_raises_on_a_broken_provider(self):
        class Boom(ModelProvider):
            manifest = Manifest(id="boom", capability="model", version="0")
            async def initialize(self):
                raise RuntimeError("kaboom")
        reg = Registry(); reg.register_all(fake.ALL); reg.register(Boom)
        report = asyncio.run(Kernel.load(None, profile="local", overrides={"model": "boom"}, registry=reg).doctor())
        row = next(r for r in report.rows if r.capability == "model")
        self.assertEqual(row.status, "ERROR")
        self.assertIn("kaboom", row.detail)


if __name__ == "__main__":
    unittest.main()
