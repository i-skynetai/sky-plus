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
    def test_init_doctor_run_inspect_swap(self):
        with tempfile.TemporaryDirectory() as d:
            cwd = os.getcwd(); os.chdir(d)
            try:
                code, out = run("init"); self.assertEqual(code, 0); self.assertTrue(Path("skynet.yaml").exists())
                code, out = run("init"); self.assertEqual(code, 1)
                code, out = run("doctor"); self.assertEqual(code, 0, out); self.assertIn("verdict: OK", out)
                code, out = run("run", "say hello", "--json"); self.assertEqual(code, 0, out); self.assertIn('"status": "ok"', out)
                code, out = run("inspect"); self.assertEqual(code, 0); self.assertIn('"kind": "run"', out)
                code, out = run("swap", "model", "litellm"); self.assertEqual(code, 1); self.assertIn("refused", out)
                code, out = run("swap", "model", "litellm", "--force"); self.assertEqual(code, 0)
                code, out = run("doctor"); self.assertEqual(code, 1); self.assertIn("MISSING", out)
                code, out = run("providers"); self.assertEqual(code, 0); self.assertIn("agent-runtime", out)
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


if __name__ == "__main__":
    unittest.main()
