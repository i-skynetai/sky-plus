"""The run record: append-only, kernel-owned, written as JSON lines.

A provider receives a `RecorderHandle` that can only append events. It cannot read, edit
or delete what was recorded. That is the audit property Skynet+ promises: the model never
writes its own report card.
"""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .contracts import Result, Task


def _json_safe(value: Any) -> Any:
    try:
        json.dumps(value)
        return value
    except (TypeError, ValueError):
        return repr(value)


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
    events: list[dict] = field(default_factory=list)
    result: dict | None = None

    def to_dict(self) -> dict:
        return {"kind": "run", "run_id": self.run_id, "agent": self.agent, "task_id": self.task_id,
                "task_input": _json_safe(self.task_input), "profile": self.profile,
                "providers": self.providers, "started": self.started, "finished": self.finished,
                "events": self.events, "result": self.result}


class RecorderHandle:
    """What a provider gets: append only."""

    def __init__(self, recorder: "Recorder") -> None:
        self._recorder = recorder

    def event(self, kind: str, **data: Any) -> None:
        self._recorder.event(kind, **data)

    @property
    def run_id(self) -> str:
        return self._recorder.record.run_id


class Recorder:
    def __init__(self, record: RunRecord, path: Path | None) -> None:
        self.record = record
        self.path = path
        self.handle = RecorderHandle(self)
        if path is not None:
            path.parent.mkdir(parents=True, exist_ok=True)

    def event(self, kind: str, **data: Any) -> None:
        entry = {"at": time.time(), "kind": kind, **{k: _json_safe(v) for k, v in data.items()}}
        self.record.events.append(entry)
        self._append({"kind": "event", "run_id": self.record.run_id, **entry})

    def finish(self, result: Result) -> None:
        self.record.finished = time.time()
        self.record.result = _json_safe(result.to_dict())
        self._append(self.record.to_dict())

    def _append(self, line: dict) -> None:
        if self.path is None:
            return
        try:
            with self.path.open("a") as fh:
                fh.write(json.dumps(line, sort_keys=True) + "\n")
        except OSError:
            pass   # recording must never fail the run; the in-memory record still exists


def new_record(agent: str, task: Task, profile: str, providers: dict[str, str]) -> RunRecord:
    return RunRecord(run_id=f"run-{uuid.uuid4().hex[:12]}", agent=agent, task_id=task.id,
                     task_input=task.input, profile=profile, providers=providers)


def read_runs(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    runs = []
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if entry.get("kind") == "run":
            runs.append(entry)
    return runs


def find_run(path: Path, run_id: str | None = None) -> dict | None:
    runs = read_runs(path)
    if not runs:
        return None
    if run_id is None:
        return runs[-1]
    return next((r for r in runs if r["run_id"] == run_id), None)
