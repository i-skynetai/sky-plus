import os, tempfile, unittest
from pathlib import Path
from _path import *  # noqa
from skynet_plus.core.config import find_config, load, render_default
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

    def test_the_readme_example_loads(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "skynet.yaml"
            p.write_text("profile: development\nagent-runtime: {provider: langgraph}\n"
                         "model:         {provider: litellm, model: ${SKYNET_MODEL:gpt-4o-mini}}\n"
                         "memory:        {provider: mem0}\n")
            cfg = load(p)
            self.assertEqual(cfg.provider_id("agent-runtime"), "langgraph")
            self.assertEqual(cfg.capabilities["model"], {"provider": "litellm", "model": "gpt-4o-mini"})

    def test_no_file_means_the_named_profile(self):
        cfg = load(None, profile="development")
        self.assertEqual(cfg.provider_id("agent-runtime"), "langgraph")
        self.assertNotIn("decision", cfg.capabilities)

    def test_config_mistakes_are_config_errors_that_name_the_file(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "skynet.yaml"
            cases = ["profile: local\nbanana: 1\n",
                     "profile: local\nrequirements:\n  streamng: true\n",
                     "profile: local\nrequirements:\n  memry: {persistent: true}\n",
                     "profile: local\nmodel: '{provider: x}'\n",
                     "profile: local\nmodel:\n  provider: fake\n  key: ${SKYNET_NOPE}\n",
                     "profile: local\nmodel: &a fake\n"]
            os.environ.pop("SKYNET_NOPE", None)
            for text in cases:
                p.write_text(text)
                with self.assertRaises(ConfigError, msg=text) as cm:
                    load(p)
                self.assertIn("skynet.yaml", str(cm.exception), text)

    def test_run_log_is_relative_to_the_config_file_not_the_cwd(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d).resolve(); (root / "skynet.yaml").write_text("profile: local\nrun_log: .skynet/runs.jsonl\n")
            sub = root / "sub"; sub.mkdir()
            cwd = os.getcwd(); os.chdir(sub)
            try:
                cfg = load(root / "skynet.yaml")
                self.assertEqual(Path(cfg.run_log), root / ".skynet" / "runs.jsonl")
                self.assertTrue(Path(cfg.run_log).is_absolute())
            finally:
                os.chdir(cwd)

    def test_the_env_run_log_applies_only_when_the_file_sets_none(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "skynet.yaml"; p.write_text("profile: local\n")
            self.assertEqual(load(p).run_log, os.environ["SKYNET_RUN_LOG"])
            p.write_text("profile: local\nrun_log: mine.jsonl\n")
            self.assertEqual(Path(load(p).run_log), Path(d).resolve() / "mine.jsonl")

    def test_search_checks_this_folder_but_not_parents_when_disabled(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d).resolve(); (root / "skynet.yaml").write_text("profile: local\n")
            sub = root / "sub"; sub.mkdir()
            self.assertEqual(find_config(root), root / "skynet.yaml")
            self.assertIsNone(find_config(sub))               # SKYNET_CONFIG_SEARCH=0 in tests
            os.environ["SKYNET_CONFIG_SEARCH"] = "1"
            try:
                self.assertEqual(find_config(sub), root / "skynet.yaml")
                (sub / ".git").mkdir()                          # a repository boundary stops the walk
                self.assertIsNone(find_config(sub))
            finally:
                os.environ["SKYNET_CONFIG_SEARCH"] = "0"

    def test_render_default_is_loadable(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "skynet.yaml"; p.write_text(render_default("local"))
            self.assertEqual(load(p).provider_id("model"), "fake")

    def test_text_is_checked_without_touching_the_file(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "skynet.yaml"; p.write_text("profile: local\n")
            cfg = load(p, text="profile: local\nmodel: {provider: litellm}\n")
            self.assertEqual(cfg.provider_id("model"), "litellm")
            self.assertEqual(p.read_text(), "profile: local\n")


if __name__ == "__main__":
    unittest.main()
