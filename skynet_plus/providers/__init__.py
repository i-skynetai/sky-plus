"""Built-in providers.

The fakes and the rules guardrail always load. Real adapters live here too, one module
each, and load only when their library is installed (decision SP-020); a missing library
is reported by `skynet doctor` as a MISSING row with the install hint, never as an
import error at startup.
"""
from __future__ import annotations

import importlib

# module name -> (class name, pip extra)
OPTIONAL: dict[str, tuple[str, str]] = {
    "langgraph_runtime": ("LangGraphRuntime", "langgraph"),
    "litellm_model": ("LiteLLMModel", "litellm"),
    "mem0_memory": ("Mem0Memory", "mem0"),
    "otel_telemetry": ("OpenTelemetryTelemetry", "otel"),
    "deepeval_evaluation": ("DeepEvalEvaluation", "deepeval"),
}


def optional_providers() -> tuple[list[type], dict[str, str]]:
    """(loaded provider classes, {module: reason it was skipped})."""
    loaded: list[type] = []
    skipped: dict[str, str] = {}
    for module, (attr, extra) in OPTIONAL.items():
        try:
            mod = importlib.import_module(f"{__name__}.{module}")
            loaded.append(getattr(mod, attr))
        except ImportError as exc:
            skipped[module] = f'{exc} — pip install "skynet-plus[{extra}]"'
    return loaded, skipped
