"""The run record: append-only JSON lines, hash-chained, kernel-owned.

A provider receives a handle that can only append an event. Every line on disk carries
the hash of the line before it and its own hash, so `skynet inspect` rebuilds a run from
the lines as they were written and reports where a chain is broken. Inside one process
nothing can be made impossible; this makes tampering visible, which is the promise.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from .contracts import Result, Task

_CHAIN_FIELDS = ("prev", "hash")


def _json_safe(value: Any) -> Any:
    try:
        json.dumps(value)
        return value
    except (TypeError, ValueError):
        return repr(value)


def _digest(line: dict) -> str:
    body = {k: v for k, v in line.items() if k != "hash"}
    return hashlib.sha256(json.dumps(body, sort_keys=True, default=str).encode()).hexdigest()


@dataclass
class RunRecord:
    run_id: str
    agent: str
    task_id: str
    task_input: Any
    profile: str
    providers: dict[str, str]            # capability -> provider@version
    started: float = field(default_factory=time.time)
    finished: float | None = None
    events: list[dict] = field(default_factory=list)   # {"name", "at", "data"} — the in-memory copy
    result: dict | None = None

    def header(self) -> dict:
        return {"kind": "run", "run_id": self.run_id, "agent": self.agent, "task_id": self.task_id,
                "task_input": _json_safe(self.task_input), "profile": self.profile,
                "providers": self.providers, "started": self.started, "finished": self.finished,
                "result": self.result}

    def to_dict(self) -> dict:
        return {**self.header(), "events": list(self.events)}


class RecorderHandle:
    """What a provider gets: append one event. Nothing else."""

    def __init__(self, append: Callable[[str, dict], None], run_id: str) -> None:
        self._append = append
        self._run_id = run_id

    def event(self, name: str, **data: Any) -> None:
        self._append(name, data)

    @property
    def run_id(self) -> str:
        return self._run_id


def _last_hash(path: Path) -> str:
    """The hash of the last line already in the file, so chains continue across runs."""
    try:
        with path.open("rb") as fh:
            fh.seek(0, os.SEEK_END)
            size = fh.tell()
            if size == 0:
                return ""
            step = min(size, 65536)
            fh.seek(size - step)
            tail = fh.read().splitlines()
        for raw in reversed(tail):
            if raw.strip():
                return json.loads(raw).get("hash", "")
    except (OSError, json.JSONDecodeError):
        return ""
    return ""


class Recorder:
    def __init__(self, record: RunRecord, path: Path | None) -> None:
        self.record = record
        self.path = path
        self.handle = RecorderHandle(self._event, record.run_id)
        self._prev = ""
        if path is not None:
            path.parent.mkdir(parents=True, exist_ok=True)
            self._prev = _last_hash(path)

    def event(self, name: str, **data: Any) -> None:
        self._event(name, data)

    def _event(self, name: str, data: dict) -> None:
        entry = {"name": str(name), "at": time.time(), "data": {k: _json_safe(v) for k, v in data.items()}}
        self.record.events.append(entry)
        self._write({"kind": "event", "run_id": self.record.run_id, **entry})

    def finish(self, result: Result) -> None:
        self.record.finished = time.time()
        self.record.result = _json_safe(result.to_dict())
        self._write(self.record.header())

    def _write(self, line: dict) -> None:
        if self.path is None:
            return
        line = {**line, "prev": self._prev}
        line["hash"] = _digest(line)
        try:
            with self.path.open("a") as fh:
                fh.write(json.dumps(line, sort_keys=True) + "\n")
            self._prev = line["hash"]
        except OSError:
            pass   # recording must never fail the run; the in-memory record still exists


def new_record(agent: str, task: Task, profile: str, providers: dict[str, str]) -> RunRecord:
    return RunRecord(run_id=f"run-{uuid.uuid4().hex[:12]}", agent=agent, task_id=task.id,
                     task_input=task.input, profile=profile, providers=providers)


# -- reading ------------------------------------------------------------------------------
def read_lines(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    out = []
    for raw in path.read_text().splitlines():
        if not raw.strip():
            continue
        try:
            out.append(json.loads(raw))
        except json.JSONDecodeError:
            out.append({"kind": "corrupt", "raw": raw})
    return out


def verify(path: Path) -> list[str]:
    """Problems with the chain, in order. Empty means every line is as it was written."""
    problems = []
    prev = ""
    for n, line in enumerate(read_lines(path), start=1):
        if line.get("kind") == "corrupt":
            problems.append(f"line {n}: not JSON")
            prev = ""
            continue
        if line.get("prev", "") != prev:
            problems.append(f"line {n}: chain broken — a line before it was changed or removed")
        if line.get("hash") != _digest(line):
            problems.append(f"line {n}: hash mismatch — the line was edited")
        prev = _digest(line)          # what the next line must point at: the line as it is now
    return problems


def read_runs(path: Path) -> list[dict]:
    """Runs rebuilt from the event lines, in the order their headers were written."""
    events: dict[str, list[dict]] = {}
    runs = []
    for line in read_lines(path):
        kind = line.get("kind")
        if kind == "event":
            events.setdefault(line.get("run_id", ""), []).append(
                {"name": line.get("name"), "at": line.get("at"), "data": line.get("data", {})})
        elif kind == "run":
            run = {k: v for k, v in line.items() if k not in _CHAIN_FIELDS}
            run["events"] = events.get(run.get("run_id", ""), [])
            runs.append(run)
    return runs


def find_run(path: Path, run_id: str | None = None) -> dict | None:
    runs = read_runs(path)
    if not runs:
        return None
    if run_id is None:
        return runs[-1]
    return next((r for r in runs if r["run_id"] == run_id), None)
