"""Curated stacks. A profile is only a dict of capability -> provider config; a file overrides it."""
from __future__ import annotations

from copy import deepcopy

LOCAL_CAPABILITIES = ("agent-runtime", "model", "memory", "decision",
                      "guardrail", "evaluation", "telemetry")

PROFILES: dict[str, dict[str, dict]] = {
    # Runs with no installs and no keys. In-memory fakes for everything.
    "local": {cap: {"provider": "fake"} for cap in LOCAL_CAPABILITIES},
    # The intended default stack. Each provider is a pip extra; doctor says which are missing.
    "development": {
        "agent-runtime": {"provider": "langgraph"},
        "model": {"provider": "litellm", "model": "${SKYNET_MODEL:gpt-4o-mini}"},
        "memory": {"provider": "mem0"},
        "decision": {"provider": "praxis"},
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

# provider id -> the pip extra that ships it (used by doctor's install hint)
EXTRAS: dict[tuple[str, str], str] = {
    ("agent-runtime", "langgraph"): "langgraph",
    ("model", "litellm"): "litellm",
    ("memory", "mem0"): "mem0",
    ("memory", "graphiti"): "graphiti",
    ("decision", "praxis"): "praxis",
    ("guardrail", "nemo"): "nemo",
    ("evaluation", "deepeval"): "deepeval",
    ("telemetry", "opentelemetry"): "otel",
    ("authorization", "openfga"): "openfga",
    ("workflow", "temporal"): "temporal",
}


def profile(name: str) -> dict[str, dict]:
    try:
        return deepcopy(PROFILES[name])
    except KeyError:
        raise KeyError(f"unknown profile {name!r}; known: {sorted(PROFILES)}") from None


def install_hint(capability: str, provider_id: str) -> str:
    extra = EXTRAS.get((capability, provider_id))
    return f'pip install "skynet-plus[{extra}]"' if extra else f"no package known for {provider_id!r}"
