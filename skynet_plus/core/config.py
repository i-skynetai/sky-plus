"""skynet.yaml: profile + per-capability overrides + requirements, with `${ENV:default}` expansion."""
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
_ENV = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::([^}]*))?\}")


@dataclass
class Config:
    profile: str = "local"
    capabilities: dict[str, dict] = field(default_factory=dict)
    requirements: dict[str, dict[str, bool]] = field(default_factory=dict)
    run_log: str = ".skynet/runs.jsonl"
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
    here = (start or Path.cwd()).resolve()
    for directory in (here, *here.parents):
        for name in CONFIG_NAMES:
            candidate = directory / name
            if candidate.is_file():
                return candidate
    return None


def parse_file(path: Path) -> dict:
    text = path.read_text()
    try:
        data = json.loads(text) if path.suffix == ".json" else miniyaml.loads(text)
    except (json.JSONDecodeError, miniyaml.YAMLError) as exc:
        raise ConfigError(f"{path}: {exc}") from exc
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ConfigError(f"{path}: top level must be a mapping")
    return data


def load(path: str | Path | None = None, profile: str | None = None,
         overrides: dict | None = None, requirements: dict | None = None) -> Config:
    """Build the effective configuration: profile defaults ← file ← overrides."""
    source = Path(path) if path else find_config()
    raw = parse_file(source) if source else {}
    name = profile or raw.get("profile") or "local"
    try:
        caps = load_profile(name)
    except KeyError as exc:
        raise ConfigError(str(exc)) from None

    for key, value in raw.items():
        if key in CAPABILITIES:
            if value is None or value is False:
                caps.pop(key, None)                      # `memory: null` switches it off
            elif isinstance(value, dict):
                caps.setdefault(key, {}).update(value)
            elif isinstance(value, str):
                caps[key] = {"provider": value}          # `model: litellm` shorthand
            else:
                raise ConfigError(f"{source}: section {key!r} must be a mapping or a provider id")
    for key, value in (overrides or {}).items():
        if key in CAPABILITIES:
            caps.setdefault(key, {}).update(value if isinstance(value, dict) else {"provider": value})

    unknown = [k for k in raw if k not in CAPABILITIES and k not in ("profile", "requirements", "run_log")]
    if unknown:
        raise ConfigError(f"{source}: unknown top-level keys {unknown}; capabilities are {CAPABILITIES}")

    for cap, section in caps.items():
        if "provider" not in section:
            raise ConfigError(f"capability {cap!r} has no provider")

    reqs = normalise_requirements(raw.get("requirements"))
    for cap, feats in normalise_requirements(requirements).items():
        reqs.setdefault(cap, {}).update(feats)

    return Config(profile=name, capabilities=expand_env(caps), requirements=reqs,
                  run_log=raw.get("run_log", ".skynet/runs.jsonl"), source=source, raw=deepcopy(raw))


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
              "", "run_log: .skynet/runs.jsonl", ""]
    return "\n".join(lines)
