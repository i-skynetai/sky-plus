import contextlib, io, os, tempfile, unittest
from pathlib import Path
from _path import *  # noqa
from skynet_plus import cli


def run(*argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = cli.main(list(argv))
    return code, out.getvalue()


class TheCli(unittest.TestCase):
    def test_init_doctor_run_inspect_eval_swap(self):
        with tempfile.TemporaryDirectory() as d:
            cwd = os.getcwd(); os.chdir(d)
            try:
                code, out = run("init"); self.assertEqual(code, 0); self.assertTrue(Path("skynet.yaml").exists())
                code, out = run("init"); self.assertEqual(code, 1)
                code, out = run("doctor"); self.assertEqual(code, 0, out); self.assertIn("verdict: OK", out)
                code, out = run("run", "say hello", "--json"); self.assertEqual(code, 0, out); self.assertIn('"status": "ok"', out)
                self.assertTrue(Path(d, ".skynet", "runs.jsonl").exists())        # next to the config
                code, out = run("inspect"); self.assertEqual(code, 0, out); self.assertIn('"chain": "ok"', out)
                code, out = run("eval"); self.assertEqual(code, 0, out); self.assertIn('"completed": 1.0', out)
                Path("skynet.yaml").write_text(Path("skynet.yaml").read_text().replace(
                    "decision:\n  provider: fake", "decision: {provider: fake, threshold: 0.9}   # keep"))
                code, out = run("swap", "model", "no-such-model"); self.assertEqual(code, 1); self.assertIn("refused", out)
                code, out = run("swap", "model", "no-such-model", "--force"); self.assertEqual(code, 0)
                text = Path("skynet.yaml").read_text()
                self.assertIn("# Skynet+ configuration", text)                       # comments kept
                self.assertIn("threshold: 0.9", text)                                # other keys kept
                self.assertIn("# keep", text)
                code, out = run("doctor"); self.assertEqual(code, 1); self.assertIn("MISSING", out)
                code, out = run("providers"); self.assertEqual(code, 0); self.assertIn("agent-runtime", out)
            finally:
                os.chdir(cwd)

    def test_a_config_mistake_is_one_line_and_exit_2(self):
        with tempfile.TemporaryDirectory() as d:
            cwd = os.getcwd(); os.chdir(d)
            try:
                Path("skynet.yaml").write_text("profile: local\nrequirements:\n  streamng: true\n")
                err = io.StringIO()
                with contextlib.redirect_stderr(err):
                    code, out = run("doctor")
                self.assertEqual(code, 2)
                self.assertIn("streamng", out + err.getvalue())
                self.assertNotIn("Traceback", out + err.getvalue())
                with contextlib.redirect_stderr(err):
                    code, out = run("run", "hi")
                self.assertEqual(code, 2)
            finally:
                os.chdir(cwd)

    def test_doctor_on_development_profile_is_not_ready_but_does_not_crash(self):
        with tempfile.TemporaryDirectory() as d:
            cwd = os.getcwd(); os.chdir(d)
            try:
                code, out = run("doctor", "--profile", "development", "--json")
                self.assertEqual(code, 1); self.assertIn('"ok": false', out)
            finally:
                os.chdir(cwd)

    def test_inspect_reports_a_broken_chain(self):
        with tempfile.TemporaryDirectory() as d:
            cwd = os.getcwd(); os.chdir(d)
            try:
                run("init"); run("run", "hello")
                log = Path(d, ".skynet", "runs.jsonl")
                lines = log.read_text().splitlines(); lines.pop(0); log.write_text("\n".join(lines) + "\n")
                code, out = run("inspect")
                self.assertEqual(code, 1); self.assertIn("chain broken", out)
            finally:
                os.chdir(cwd)


class HintsAreTrue(unittest.TestCase):
    def test_every_hinted_extra_exists_in_pyproject(self):
        import re
        from skynet_plus.core.profiles import EXTRAS
        text = Path(__file__).resolve().parent.parent.joinpath("pyproject.toml").read_text()
        defined = set(re.findall(r"^(\w[\w-]*) = \[", text, re.M))
        for extra in EXTRAS.values():
            self.assertIn(extra, defined)


if __name__ == "__main__":
    unittest.main()
