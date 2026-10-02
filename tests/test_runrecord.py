import json
import tempfile
import unittest
from pathlib import Path

from _path import *  # noqa

from skynet_plus import Result
from skynet_plus.core.runrecord import Recorder, RunRecord, find_run, read_lines, read_runs, verify


def record(path, run_id="r1"):
    return Recorder(RunRecord(run_id, "agent", "task", "input", "local", {"model": "fake@0"}), path)


class TheRunRecordIsAppendOnlyAndChained(unittest.TestCase):
    def test_event_lines_carry_the_name_in_its_own_field(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d, "runs.jsonl"); rec = record(p)
            rec.event("tool.executed", tool="x", kind="smuggled")
            line = read_lines(p)[0]
            self.assertEqual(line["kind"], "event")
            self.assertEqual(line["name"], "tool.executed")
            self.assertEqual(line["data"], {"tool": "x", "kind": "smuggled"})

    def test_an_event_named_run_cannot_forge_a_run(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d, "runs.jsonl"); rec = record(p)
            rec.event("run", forged=True)
            self.assertEqual(read_runs(p), [])
            rec.finish(Result("task", "out"))
            runs = read_runs(p)
            self.assertEqual(len(runs), 1)
            self.assertEqual([e["name"] for e in runs[0]["events"]], ["run"])

    def test_inspect_rebuilds_from_disk_so_clearing_memory_changes_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d, "runs.jsonl"); rec = record(p)
            rec.event("a"); rec.event("b")
            rec.record.events.clear()                 # a misbehaving provider with a reference
            rec.finish(Result("task", "out"))
            self.assertEqual([e["name"] for e in find_run(p)["events"]], ["a", "b"])
            self.assertEqual(verify(p), [])

    def test_editing_or_deleting_a_line_breaks_the_chain_where_it_happened(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d, "runs.jsonl"); rec = record(p)
            rec.event("a"); rec.event("b"); rec.finish(Result("task", "out"))
            lines = p.read_text().splitlines()
            edited = json.loads(lines[1]); edited["data"] = {"changed": True}
            lines[1] = json.dumps(edited, sort_keys=True)
            p.write_text("\n".join(lines) + "\n")
            problems = verify(p)
            self.assertTrue(any(p_.startswith("line 2: hash mismatch") for p_ in problems), problems)
            self.assertTrue(any(p_.startswith("line 3: chain broken") for p_ in problems), problems)
            lines.pop(1); p.write_text("\n".join(lines) + "\n")
            self.assertTrue(any("line 2: chain broken" in p_ for p_ in verify(p)))

    def test_the_chain_continues_across_runs_in_one_file(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d, "runs.jsonl")
            r1 = record(p, "r1"); r1.event("a"); r1.finish(Result("t", 1))
            r2 = record(p, "r2"); r2.event("b"); r2.finish(Result("t", 2))
            self.assertEqual(verify(p), [])
            self.assertEqual([r["run_id"] for r in read_runs(p)], ["r1", "r2"])
            self.assertEqual(find_run(p, "r1")["events"][0]["name"], "a")

    def test_the_handle_only_appends(self):
        rec = record(None)
        self.assertEqual([n for n in dir(rec.handle) if not n.startswith("_")], ["event", "run_id"])


if __name__ == "__main__":
    unittest.main()


class ACutTailIsDetected(unittest.TestCase):
    def test_cutting_the_last_line_is_reported_through_the_head_file(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d, "runs.jsonl"); rec = record(p)
            rec.event("a"); rec.finish(Result("task", "out"))
            self.assertEqual(verify(p), [])
            lines = p.read_text().splitlines()
            p.write_text("\n".join(lines[:-1]) + "\n")
            problems = verify(p)
            self.assertTrue(any("tail was cut" in x for x in problems), problems)
            self.assertEqual(read_runs(p), [])            # the run header is gone ...
            self.assertTrue(problems)                      # ... and inspect would say why

    def test_a_log_without_a_head_file_says_a_cut_tail_cannot_be_detected(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d, "runs.jsonl"); rec = record(p); rec.event("a")
            Path(d, "runs.jsonl.head").unlink()
            self.assertTrue(any("no head file" in x for x in verify(p)))

    def test_the_head_file_survives_a_second_recorder(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d, "runs.jsonl")
            r1 = record(p, "r1"); r1.event("a"); r1.finish(Result("t", 1))
            r2 = record(p, "r2"); r2.event("b"); r2.finish(Result("t", 2))
            self.assertEqual(verify(p), [])
            self.assertEqual(json.loads(Path(d, "runs.jsonl.head").read_text())["lines"], 4)


class AKeyedChainCannotBeRecomputedWithoutTheKey(unittest.TestCase):
    def test_hmac_when_the_key_is_set(self):
        import os
        from unittest import mock
        with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ, {"SKYNET_LOG_KEY": "secret"}):
            p = Path(d, "runs.jsonl"); rec = record(p); rec.event("a"); rec.finish(Result("t", 1))
            self.assertEqual(verify(p), [])
            os.environ.pop("SKYNET_LOG_KEY")
            self.assertTrue(any("hash mismatch" in x for x in verify(p)))   # without the key, nothing checks out
