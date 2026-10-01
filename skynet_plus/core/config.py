"""skynet.yaml: profile + per-capability overrides + requirements, with `${ENV:default}` expansion.

Environment variables the loader honours: `SKYNET_CONFIG` (a config file path, used
when no path is given), `SKYNET_CONFIG_SEARCH=0` (do not look in parent folders),
`SKYNET_RUN_LOG` (the run log path when the file does not set one).
"""
from __future__ import annotations

import json
import os
import re
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import miniyaml
from .contracts import normalise_requirements
from .errors import ConfigError
from .profiles import profile as load_profile
from .provider import CAPABILITIES

CONFIG_NAMES = ("skynet.yaml", "skynet.yml", "skynet.json")
DEFAULT_RUN_LOG = ".skynet/runs.jsonl"
TOP_LEVEL_KEYS = ("profile", "requirements", "run_log")
_ENV = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::([^}]*))?\}")
_PROVIDER_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*")


@dataclass
class Config:
    profile: str = "local"
    capabilities: dict[str, dict] = field(default_factory=dict)
    requirements: dict[str, dict[str, bool]] = field(default_factory=dict)
    run_log: str = DEFAULT_RUN_LOG           # always absolute after load()
    source: Path | None = None
    raw: dict = field(default_factory=dict)

    def provider_id(self, capability: str) -> str | None:
        section = self.capabilities.get(capability)
        return section.get("provider") if section else None


def expand_env(value: Any) -> Any:
    if isinstance(value, str):
        def sub(m: re.Match) -> str:
            name, default = m.group(1), m.group(2)
            if name in os.environ:
                return os.environ[name]
            if default is not None:
                return default
            raise ConfigError(f"environment variable {name} is not set and has no default")
        return _ENV.sub(sub, value)
    if isinstance(value, dict):
        return {k: expand_env(v) for k, v in value.items()}
    if isinstance(value, list):
        return [expand_env(v) for v in value]
    return value


def find_config(start: Path | None = None) -> Path | None:
    """The config file for this folder: `SKYNET_CONFIG`, else here, else the parents up to the
    repository root (a folder holding `.git`) unless `SKYNET_CONFIG_SEARCH=0`."""
    explicit = os.environ.get("SKYNET_CONFIG")
    if explicit:
        return Path(explicit)
    here = (start or Path.cwd()).resolve()
    search_up = os.environ.get("SKYNET_CONFIG_SEARCH", "1") != "0"
    for directory in (here, *here.parents):
        for name in CONFIG_NAMES:
            candidate = directory / name
            if candidate.is_file():
                return candidate
        if not search_up or (directory / ".git").exists():
            break
    return None


def parse_text(text: str, source: Path | None) -> dict:
    where = str(source) if source else "<config>"
    try:
        data = json.loads(text) if source and source.suffix == ".json" else miniyaml.loads(text)
    except (json.JSONDecodeError, miniyaml.YAMLError) as exc:
        raise ConfigError(f"{where}: {exc}") from exc
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ConfigError(f"{where}: top level must be a mapping")
    return data


def parse_file(path: Path) -> dict:
    return parse_text(path.read_text(), path)


def _resolve_run_log(value: str | None, source: Path | None) -> str:
    chosen = value or os.environ.get("SKYNET_RUN_LOG") or DEFAULT_RUN_LOG
    path = Path(chosen).expanduser()
    if not path.is_absolute():
        base = source.resolve().parent if (source and value) else (source.resolve().parent if source else Path.cwd())
        path = base / path
    return str(path)


def load(path: str | Path | None = None, profile: str | None = None,
         overrides: dict | None = None, requirements: dict | None = None,
         text: str | None = None) -> Config:
    """Build the effective configuration: profile defaults ← file ← overrides.

    `text` parses that text instead of reading `path` (used to check a file before it is
    written); `path` is then only the name reported in errors and the base for `run_log`.
    """
    source = Path(path) if path else (None if text is not None else find_config())
    where = str(source) if source else "<config>"
    raw = parse_text(text, source) if text is not None else (parse_file(source) if source else {})
    name = profile or raw.get("profile") or "local"
    if not isinstance(name, str):
        raise ConfigError(f"{where}: profile must be a name")
    try:
        caps = load_profile(name)
    except KeyError as exc:
        raise ConfigError(f"{where}: {exc}") from None

    # A file's provider sections belong to the profile the file names. Asking for another
    # profile explicitly (`--profile local`, `Agent(profile="local")`) means that profile's
    # own stack; the file still supplies requirements and the run log.
    file_profile = raw.get("profile")
    apply_sections = profile is None or file_profile in (None, profile)
    for key, value in raw.items():
        if key in CAPABILITIES:
            if not apply_sections:
                continue
            if value is None or value is False:
                caps.pop(key, None)                      # `memory: null` switches it off
            elif isinstance(value, dict):
                caps.setdefault(key, {}).update(value)
            elif isinstance(value, str):
                caps[key] = {"provider": value}          # `model: litellm` shorthand
            else:
                raise ConfigError(f"{where}: section {key!r} must be a mapping or a provider id")
    for key, value in (overrides or {}).items():
        if key in CAPABILITIES:
            if value is None:
                caps.pop(key, None)
            else:
                caps.setdefault(key, {}).update(value if isinstance(value, dict) else {"provider": value})
        elif key == "run_log":
            raw = {**raw, "run_log": value}
        else:
            raise ConfigError(f"override {key!r} is not a capability; capabilities are {CAPABILITIES}")

    unknown = [k for k in raw if k not in CAPABILITIES and k not in TOP_LEVEL_KEYS]
    if unknown:
        raise ConfigError(f"{where}: unknown top-level keys {unknown}; capabilities are {CAPABILITIES}")

    for cap, section in caps.items():
        pid = section.get("provider")
        if not isinstance(pid, str) or not _PROVIDER_ID.fullmatch(pid):
            raise ConfigError(f"{where}: capability {cap!r} needs a provider id made of letters, digits, "
                              f"'.', '_' or '-'; got {pid!r}")

    try:
        reqs = normalise_requirements(raw.get("requirements"))
        for cap, feats in normalise_requirements(requirements).items():
            reqs.setdefault(cap, {}).update(feats)
    except ConfigError as exc:
        raise ConfigError(f"{where}: requirements: {exc}") from None

    run_log_value = raw.get("run_log")
    if run_log_value is not None and not isinstance(run_log_value, str):
        raise ConfigError(f"{where}: run_log must be a path")
    try:
        caps = expand_env(caps)
    except ConfigError as exc:
        raise ConfigError(f"{where}: {exc}") from None
    return Config(profile=name, capabilities=caps, requirements=reqs,
                  run_log=_resolve_run_log(run_log_value, source), source=source, raw=deepcopy(raw))


def render_default(profile_name: str = "local") -> str:
    """The file `skynet init` writes: the profile, with every section spelled out for editing."""
    caps = load_profile(profile_name)
    lines = ["# Skynet+ configuration. Change a provider here; run `skynet doctor` to check it.",
             f"profile: {profile_name}", ""]
    for cap in CAPABILITIES:
        if cap in caps:
            lines.append(miniyaml.dumps({cap: caps[cap]}).rstrip())
        else:
            lines.append(f"# {cap}: {{provider: ...}}")
    lines += ["", "# requirements:", "#   streaming: true", "#   human_approval: true",
              "", f"run_log: {DEFAULT_RUN_LOG}", ""]
    return "\n".join(lines)
