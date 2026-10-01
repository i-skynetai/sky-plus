import unittest

from _path import *  # noqa

from skynet_plus import __version__
from skynet_plus.core.provider import Manifest, Provider, version_in_range
from skynet_plus.core.registry import Registry
from skynet_plus.core.resolver import resolve
from skynet_plus.providers import fake


def local():
    return {cap: {"provider": "fake"} for cap in ("agent-runtime", "model", "memory", "telemetry")}


class VersionRanges(unittest.TestCase):
    def test_ranges(self):
        self.assertTrue(version_in_range("0.1.0", ">=0.1,<1"))
        self.assertTrue(version_in_range("0.1.0", ">=0.1"))
        self.assertFalse(version_in_range("1.0.0", ">=0.1,<1"))
        self.assertFalse(version_in_range("0.0.9", ">=0.1"))
        self.assertTrue(version_in_range("2.3.4", ""))

    def test_compatible_release(self):
        self.assertTrue(version_in_range("0.2.5", "~=0.2"))
        self.assertTrue(version_in_range("0.3.0", "~=0.2"))      # ~=0.2 means >=0.2, <1
        self.assertFalse(version_in_range("1.0.0", "~=0.2"))
        self.assertTrue(version_in_range("1.4.9", "~=1.4.2"))
        self.assertFalse(version_in_range("1.5.0", "~=1.4.2"))
        self.assertTrue(version_in_range("0.2.0", "==0.2.*"))

    def test_an_unreadable_clause_raises_a_readable_error(self):
        with self.assertRaises(ValueError) as cm:
            version_in_range("1.0", "^1.0")
        self.assertIn("^1.0", str(cm.exception))


class TheResolverChecksBeforeAnythingRuns(unittest.TestCase):
    def setUp(self):
        self.reg = Registry()
        self.reg.register_all(fake.ALL)

    def test_local_profile_resolves_with_model_before_runtime(self):
        res = resolve(self.reg, local(), {}, __version__)
        self.assertTrue(res.ok, res.problems)
        order = [b.capability for b in res.bindings]
        self.assertLess(order.index("model"), order.index("agent-runtime"))
        self.assertEqual(len(order), 4)

    def test_a_missing_provider_is_named_with_an_install_hint(self):
        caps = local(); caps["model"] = {"provider": "litellm"}
        res = resolve(self.reg, caps, {}, __version__)
        self.assertFalse(res.ok)
        p = res.problems[0]
        self.assertEqual((p.capability, p.kind), ("model", "missing-provider"))
        self.assertIn("skynet-plus[litellm]", p.detail)

    def test_a_planned_provider_says_so_instead_of_an_install_command(self):
        caps = local(); caps["memory"] = {"provider": "graphiti"}
        res = resolve(self.reg, caps, {}, __version__)
        self.assertIn("SP-050", res.problems[0].detail)
        self.assertNotIn("pip install", res.problems[0].detail)

    def test_a_required_feature_the_provider_lacks_is_refused(self):
        res = resolve(self.reg, local(), {"agent-runtime": {"streaming": True}}, __version__)
        self.assertFalse(res.ok)
        self.assertEqual(res.problems[0].kind, "missing-feature")
        self.assertIn("streaming", res.problems[0].detail)

    def test_a_requirement_on_an_unconfigured_capability_is_a_dependency_problem(self):
        res = resolve(self.reg, local(), {"decision": {"calibrated": True}}, __version__)
        self.assertEqual(res.problems[0].kind, "dependency")

    def test_an_incompatible_or_unreadable_api_range_is_refused_not_a_crash(self):
        class Old(Provider):
            manifest = Manifest(id="old", capability="model", version="9", skynet_api=">=5")

        class Odd(Provider):
            manifest = Manifest(id="odd", capability="model", version="9", skynet_api="^1.0")
        self.reg.register(Old); self.reg.register(Odd)
        for pid in ("old", "odd"):
            caps = local(); caps["model"] = {"provider": pid}
            res = resolve(self.reg, caps, {}, __version__)
            self.assertEqual(res.problems[0].kind, "incompatible", pid)

    def test_a_runtime_without_its_model_dependency_is_refused(self):
        caps = local(); del caps["model"]
        res = resolve(self.reg, caps, {}, __version__)
        self.assertEqual(res.problems[0].kind, "dependency")
        self.assertIn("model", res.problems[0].detail)


if __name__ == "__main__":
    unittest.main()
