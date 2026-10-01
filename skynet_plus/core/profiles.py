"""Curated stacks. A profile is only a dict of capability -> provider config; a file overrides it."""
from __future__ import annotations

from copy import deepcopy

LOCAL_CAPABILITIES = ("agent-runtime", "model", "memory", "decision",
                      "guardrail", "evaluation", "telemetry")

PROFILES: dict[str, dict[str, dict]] = {
    # Runs with no installs and no keys. In-memory fakes for everything.
    "local": {cap: {"provider": "fake"} for cap in LOCAL_CAPABILITIES},
    # The intended default stack. Each provider is a pip extra; doctor says which are missing.
    # `decision` is off until the Praxis provider exists (SP-031).
    "development": {
        "agent-runtime": {"provider": "langgraph"},
        "model": {"provider": "litellm", "model": "${SKYNET_MODEL:gpt-4o-mini}"},
        "memory": {"provider": "mem0"},
        "guardrail": {"provider": "rules"},
        "evaluation": {"provider": "deepeval"},
        "telemetry": {"provider": "opentelemetry"},
    },
}
PROFILES["production"] = {
    **deepcopy(PROFILES["development"]),
    "authorization": {"provider": "openfga"},
    "workflow": {"provider": "temporal"},
    "memory": {"provider": "graphiti"},
}

# provider -> the pip extra that ships it. Every extra here exists in pyproject.toml (tested).
EXTRAS: dict[tuple[str, str], str] = {
    ("agent-runtime", "langgraph"): "langgraph",
    ("model", "litellm"): "litellm",
    ("memory", "mem0"): "mem0",
    ("evaluation", "deepeval"): "deepeval",
    ("telemetry", "opentelemetry"): "otel",
}

# providers a profile may name that have no adapter yet -> the roadmap row that builds it
PLANNED: dict[tuple[str, str], str] = {
    ("decision", "praxis"): "SP-031",
    ("memory", "graphiti"): "SP-050",
    ("guardrail", "nemo"): "SP-050",
    ("authorization", "openfga"): "SP-050",
    ("workflow", "temporal"): "SP-050",
}


def profile(name: str) -> dict[str, dict]:
    try:
        return deepcopy(PROFILES[name])
    except KeyError:
        raise KeyError(f"unknown profile {name!r}; known: {sorted(PROFILES)}") from None


def install_hint(capability: str, provider_id: str) -> str:
    key = (capability, provider_id)
    if key in EXTRAS:
        return f'pip install "skynet-plus[{EXTRAS[key]}]"'
    if key in PLANNED:
        return f"no adapter exists yet; it is roadmap item {PLANNED[key]}"
    return f"no provider {provider_id!r} is known for {capability}; run `skynet providers`"
