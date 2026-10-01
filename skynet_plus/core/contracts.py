"""The portable domain objects. An application uses these and nothing provider-specific.

Task in, Result out; a Tool is a callable with a name; State is a bag the runtime carries;
an AgentSpec is what the SDK hands to whichever agent runtime is configured.
"""
from __future__ import annotations

import inspect
import time
import typing
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from .errors import ConfigError
from .provider import CAPABILITIES


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


@dataclass(frozen=True)
class Task:
    input: Any
    id: str = field(default_factory=lambda: _new_id("task"))
    metadata: dict = field(default_factory=dict)

    @classmethod
    def of(cls, value: Task | str | dict) -> Task:
        return value if isinstance(value, Task) else cls(input=value)

    @property
    def text(self) -> str:
        return self.input if isinstance(self.input, str) else str(self.input)


@dataclass
class Tool:
    """A callable the agent may use. `invoke` passes only the arguments the function accepts."""
    name: str
    fn: Callable[..., Any]
    description: str = ""
    parameters: dict = field(default_factory=dict)

    @classmethod
    def from_function(cls, fn: Tool | Callable[..., Any], name: str | None = None,
                      description: str | None = None) -> Tool:
        if isinstance(fn, Tool):
            return fn
        return cls(name=name or fn.__name__, fn=fn,
                   description=description or (inspect.getdoc(fn) or "").strip(),
                   parameters=parameters_schema(fn))

    def invoke(self, **kwargs: Any) -> Any:
        sig = inspect.signature(self.fn)
        accepts_any = any(p.kind == p.VAR_KEYWORD for p in sig.parameters.values())
        if not accepts_any:
            kwargs = {k: v for k, v in kwargs.items() if k in sig.parameters}
        return self.fn(**kwargs)


_JSON_TYPES: dict[Any, str] = {str: "string", int: "integer", float: "number", bool: "boolean",
                               list: "array", dict: "object", type(None): "null"}


def _json_type(annotation: Any) -> dict:
    if annotation is inspect.Parameter.empty or annotation is Any:
        return {}
    origin = typing.get_origin(annotation)
    if origin is typing.Union or (origin is not None and origin.__name__ == "UnionType"):
        options = [_json_type(a) for a in typing.get_args(annotation)]
        return {"anyOf": options} if options else {}
    if origin in (list, tuple, set, frozenset):
        args = typing.get_args(annotation)
        return {"type": "array", **({"items": _json_type(args[0])} if args else {})}
    if origin is dict:
        return {"type": "object"}
    if origin is typing.Literal:
        return {"enum": list(typing.get_args(annotation))}
    if annotation in _JSON_TYPES:
        return {"type": _JSON_TYPES[annotation]}
    return {}


def parameters_schema(fn: Callable[..., Any]) -> dict:
    """A JSON schema for the function's keyword arguments, from its resolved type hints.

    Works in modules that use postponed annotations (`from __future__ import annotations`);
    a hint that cannot be resolved becomes an untyped property rather than an error.
    """
    sig = inspect.signature(fn)
    try:
        hints = typing.get_type_hints(fn)
    except Exception:  # noqa: BLE001 — unresolvable forward reference
        hints = {}
    properties: dict[str, dict] = {}
    required: list[str] = []
    for p in sig.parameters.values():
        if p.kind not in (p.POSITIONAL_OR_KEYWORD, p.KEYWORD_ONLY):
            continue
        prop = dict(_json_type(hints.get(p.name, p.annotation)))
        if p.default is not inspect.Parameter.empty:
            plain = isinstance(p.default, (str, int, float, bool, type(None)))
            prop["default"] = p.default if plain else repr(p.default)
        else:
            required.append(p.name)
        properties[p.name] = prop
    schema: dict = {"type": "object", "properties": properties}
    if required:
        schema["required"] = required
    return schema


def tool(fn: Callable[..., Any] | None = None, *, name: str | None = None,
         description: str | None = None):
    """Decorator form: `@tool` or `@tool(name=..., description=...)`."""
    def wrap(f: Callable[..., Any]) -> Tool:
        return Tool.from_function(f, name=name, description=description)
    return wrap(fn) if fn is not None else wrap


@dataclass
class State:
    values: dict = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        return self.values.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self.values[key] = value

    def snapshot(self) -> dict:
        return dict(self.values)


@dataclass
class Step:
    kind: str
    detail: dict = field(default_factory=dict)
    at: float = field(default_factory=time.time)


@dataclass
class Result:
    task_id: str
    output: Any
    status: str = "ok"                      # ok | denied | needs_approval | error
    run_id: str | None = None
    steps: list[Step] = field(default_factory=list)
    usage: dict = field(default_factory=dict)
    served_by: dict = field(default_factory=dict)   # capability -> "provider@version"
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.status == "ok"

    def to_dict(self) -> dict:
        return {"task_id": self.task_id, "output": self.output, "status": self.status,
                "run_id": self.run_id, "usage": self.usage, "served_by": self.served_by,
                "error": self.error,
                "steps": [{"kind": s.kind, "detail": s.detail, "at": s.at} for s in self.steps]}


# Flat requirement flags a developer may pass, and the capability feature each one means.
FLAT_REQUIREMENTS: dict[str, tuple[str, str]] = {
    "streaming": ("agent-runtime", "streaming"),
    "checkpointing": ("agent-runtime", "checkpointing"),
    "human_approval": ("agent-runtime", "hitl"),
    "persistent_memory": ("memory", "persistent"),
    "temporal_memory": ("memory", "temporal"),
    "calibrated_decisions": ("decision", "calibrated"),
    "trajectory_eval": ("evaluation", "trajectory"),
}


def normalise_requirements(requirements: dict | None) -> dict[str, dict[str, bool]]:
    """Accept `{"streaming": True}` or `{"agent-runtime": {"streaming": True}}`; return the latter."""
    out: dict[str, dict[str, bool]] = {}
    for key, value in (requirements or {}).items():
        if isinstance(value, dict):
            out.setdefault(key, {}).update({k: bool(v) for k, v in value.items()})
        elif key in FLAT_REQUIREMENTS:
            cap, feature = FLAT_REQUIREMENTS[key]
            out.setdefault(cap, {})[feature] = bool(value)
        else:
            raise ConfigError(f"unknown requirement {key!r}; known flags: "
                              f"{sorted(FLAT_REQUIREMENTS)}, or a capability name with a mapping of features")
    for cap in out:
        if cap not in CAPABILITIES:
            raise ConfigError(f"requirement names unknown capability {cap!r}; capabilities are {CAPABILITIES}")
    return out


@dataclass(frozen=True)
class AgentSpec:
    name: str
    instructions: str
    tools: tuple[Tool, ...] = ()
    requirements: dict = field(default_factory=dict)   # normalised: capability -> features
    metadata: dict = field(default_factory=dict)

    def tool(self, name: str) -> Tool | None:
        return next((t for t in self.tools if t.name == name), None)
