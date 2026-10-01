import unittest
from unittest import mock
from _path import *  # noqa
from skynet_plus.core.provider import Manifest
from skynet_plus.core.registry import Registry, default_registry
from skynet_plus.providers import fake
from skynet_plus.spi import GuardrailProvider


class Impostor(GuardrailProvider):
    manifest = Manifest(id="rules", capability="guardrail", version="9", provides={"input": True})


class Newcomer(GuardrailProvider):
    manifest = Manifest(id="other", capability="guardrail", version="1", provides={"input": True})


class _EP:
    def __init__(self, name, obj):
        self.name, self._obj = name, obj

    def load(self):
        if isinstance(self._obj, Exception):
            raise self._obj
        return self._obj


class PlugInsFromOtherPackages(unittest.TestCase):
    def test_a_clash_is_refused_and_a_newcomer_is_listed(self):
        eps = [_EP("evil", Impostor), _EP("good", Newcomer), _EP("broken", ImportError("no such module"))]
        with mock.patch("skynet_plus.core.registry.metadata.entry_points", return_value=eps):
            reg = default_registry()
        self.assertIsNotNone(reg.get("guardrail", "other"))
        self.assertEqual(reg.get("guardrail", "rules").__module__, "skynet_plus.providers.rules")
        self.assertTrue(any("refused" in e and "guardrail/rules" in e for e in reg.load_errors), reg.load_errors)
        self.assertTrue(any("broken" in e for e in reg.load_errors))


if __name__ == "__main__":
    unittest.main()
