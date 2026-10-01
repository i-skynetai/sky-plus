import asyncio, unittest
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

    def test_a_running_kernel_still_checks_a_new_requirement(self):
        async def go():
            async with Kernel.load(None, profile="local") as k:
                await k.start()                                   # no-op
                with self.assertRaises(ResolutionError) as cm:
                    await k.start({"agent-runtime": {"streaming": True}})
                self.assertIn("streaming", str(cm.exception))
                with self.assertRaises(ResolutionError):
                    await k.start({"authorization": {"allow": True}})
                self.assertTrue(k.services.has("model"))          # still running
        asyncio.run(go())

    def test_an_unhealthy_provider_stops_the_start_and_closes_the_rest(self):
        closed = []

        class Sick(fake.FakeTelemetry):
            manifest = Manifest(id="sick", capability="telemetry", version="0")
            async def health(self):
                return Health(ok=False, detail="no pulse")

        class Watch(fake.FakeModel):
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

    def test_a_missing_provider_row_names_the_fix(self):
        report = asyncio.run(Kernel.load(None, profile="production", overrides={"model": "no-such-model"}).doctor())
        self.assertFalse(report.ok)
        missing = {r.capability: r for r in report.rows if r.status == "MISSING"}
        self.assertIn("no provider 'no-such-model'", missing["model"].detail)
        self.assertIn("SP-050", missing["memory"].detail)            # planned, not an install command
        self.assertIn("NOT READY", report.render())

    def test_doctor_agrees_with_start(self):
        """Doctor says OK exactly when start would succeed, on the three SP-004 cases."""
        async def go(requirements=None, **overrides):
            k = Kernel.load(None, profile="local", overrides=overrides or None)
            report = await k.doctor(requirements)
            try:
                await k.start(requirements); started = True
            except Exception:
                started = False
            finally:
                await k.stop()
            return report.ok, started
        self.assertEqual(asyncio.run(go()), (True, True))
        self.assertEqual(asyncio.run(go({"agent-runtime": {"streaming": True}})), (False, False))
        self.assertEqual(asyncio.run(go({"authorization": {"allow": True}})), (False, False))

        class Odd(ModelProvider):
            manifest = Manifest(id="odd", capability="model", version="0", skynet_api="^1")
        reg = Registry(); reg.register_all(fake.ALL); reg.register(Odd)
        k = Kernel.load(None, profile="local", overrides={"model": "odd"}, registry=reg)
        report = asyncio.run(k.doctor())
        self.assertFalse(report.ok)
        self.assertEqual(next(r for r in report.rows if r.capability == "model").status, "INCOMPATIBLE")

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
