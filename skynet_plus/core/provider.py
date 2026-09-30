"""The provider contract every adapter implements, and the manifest that describes it."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, ClassVar

CAPABILITIES: tuple[str, ...] = (
    "agent-runtime", "model", "memory", "decision", "knowledge", "code",
    "guardrail", "authorization", "workflow", "evaluation", "telemetry", "payment",
)


def _vtuple(v: str) -> tuple[int, ...]:
    parts = re.findall(r"\d+", v)
    return tuple(int(p) for p in parts) or (0,)


def version_in_range(version: str, spec: str) -> bool:
    """`spec` like ">=0.1,<2". Empty spec means any version."""
    v = _vtuple(version)
    for clause in filter(None, (c.strip() for c in spec.split(","))):
        m = re.match(r"(>=|<=|==|>|<|!=)\s*([\d.]+)", clause)
        if not m:
            raise ValueError(f"bad version clause {clause!r}")
        op, bound = m.group(1), _vtuple(m.group(2))
        # compare on the bound's precision so ">=0.1" accepts 0.1.0
        vv = v[:len(bound)] + (0,) * max(0, len(bound) - len(v))
        ok = {">=": vv >= bound, "<=": vv <= bound, "==": vv == bound,
              ">": vv > bound, "<": vv < bound, "!=": vv != bound}[op]
        if not ok:
            return False
    return True


@dataclass(frozen=True)
class Manifest:
    id: str
    capability: str
    version: str
    provides: dict = field(default_factory=dict)      # feature -> bool
    requires: tuple[str, ...] = ()                    # capabilities that must be initialised first
    skynet_api: str = ">=0.1,<1"
    package: str | None = None                        # pip extra or distribution that ships it
    description: str = ""

    def __post_init__(self) -> None:
        if self.capability not in CAPABILITIES:
            raise ValueError(f"unknown capability {self.capability!r}; one of {CAPABILITIES}")

    @property
    def ref(self) -> str:
        return f"{self.id}@{self.version}"

    def missing(self, features: dict[str, bool]) -> list[str]:
        """Which required features this provider does not declare."""
        return sorted(f for f, wanted in features.items() if wanted and not self.provides.get(f))

    def compatible_with(self, api_version: str) -> bool:
        return version_in_range(api_version, self.skynet_api)


@dataclass
class Health:
    ok: bool
    detail: str = ""
    checks: dict = field(default_factory=dict)


class Provider:
    """Base class. Subclasses set `manifest` and implement the capability's interface.

    Lifecycle: construct with config → `initialize()` → `health()` → use → `close()`.
    """
    manifest: ClassVar[Manifest]

    def __init__(self, config: dict | None = None) -> None:
        self.config: dict[str, Any] = dict(config or {})

    async def initialize(self) -> None:
        return None

    async def health(self) -> Health:
        return Health(ok=True, detail="no health check implemented")

    async def close(self) -> None:
        return None

    def __repr__(self) -> str:
        return f"<{type(self).__name__} {self.manifest.ref}>"
