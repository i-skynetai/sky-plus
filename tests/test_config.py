import os, tempfile, unittest
from pathlib import Path
from _path import *  # noqa
from skynet_plus.core.config import load, render_default
from skynet_plus.core.errors import ConfigError


class ConfigLoads(unittest.TestCase):
    def test_profile_then_file_then_overrides(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "skynet.yaml"
            p.write_text("profile: local\nmodel:\n  provider: fake\n  model: ${SKYNET_TEST_MODEL:tiny}\n"
                         "memory: null\nrequirements:\n  human_approval: true\n")
            os.environ.pop("SKYNET_TEST_MODEL", None)
            cfg = load(p, overrides={"telemetry": "fake"})
            self.assertEqual(cfg.profile, "local")
            self.assertEqual(cfg.capabilities["model"]["model"], "tiny")
            self.assertNotIn("memory", cfg.capabilities)
            self.assertEqual(cfg.requirements, {"agent-runtime": {"hitl": True}})
            os.environ["SKYNET_TEST_MODEL"] = "big"
            self.assertEqual(load(p).capabilities["model"]["model"], "big")

    def test_no_file_means_the_named_profile(self):
        cfg = load(None, profile="development")
        self.assertEqual(cfg.provider_id("agent-runtime"), "langgraph")

    def test_unknown_key_is_a_config_error(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "skynet.yaml"; p.write_text("profile: local\nbanana: 1\n")
            with self.assertRaises(ConfigError):
                load(p)

    def test_missing_env_without_default_is_a_config_error(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "skynet.yaml"; p.write_text("profile: local\nmodel:\n  provider: fake\n  key: ${SKYNET_NOPE}\n")
            os.environ.pop("SKYNET_NOPE", None)
            with self.assertRaises(ConfigError):
                load(p)

    def test_render_default_is_loadable(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "skynet.yaml"; p.write_text(render_default("local"))
            self.assertEqual(load(p).provider_id("model"), "fake")


if __name__ == "__main__":
    unittest.main()
