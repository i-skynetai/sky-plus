"""capability → provider, checked before anything is instantiated."""
from __future__ import annotations

from dataclasses import dataclass, field

from .profiles import install_hint
from .provider import Manifest, Provider
from .registry import Registry


@dataclass
class Problem:
    capability: str
    provider: str
    kind: str          # missing-provider | incompatible | missing-feature | dependency
    detail: str

    def __str__(self) -> str:
        return f"{self.capability}/{self.provider}: {self.kind}: {self.detail}"


@dataclass
class Binding:
    capability: str
    provider_cls: type[Provider]
    config: dict
    manifest: Manifest


@dataclass
class Resolution:
    bindings: list[Binding] = field(default_factory=list)   # in initialisation order
    problems: list[Problem] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems

    def binding(self, capability: str) -> Binding | None:
        return next((b for b in self.bindings if b.capability == capability), None)


def resolve(registry: Registry, capabilities: dict[str, dict],
            requirements: dict[str, dict[str, bool]], api_version: str) -> Resolution:
    res = Resolution()
    found: dict[str, Binding] = {}

    for cap, section in capabilities.items():
        pid = section.get("provider", "")
        cls = registry.get(cap, pid)
        if cls is None:
            res.problems.append(Problem(cap, pid, "missing-provider",
                                        f"not installed or not registered; try: {install_hint(cap, pid)}"))
            continue
        m = cls.manifest
        if not m.compatible_with(api_version):
            res.problems.append(Problem(cap, pid, "incompatible",
                                        f"needs skynet_api {m.skynet_api}, this is {api_version}"))
            continue
        missing = m.missing(requirements.get(cap, {}))
        if missing:
            res.problems.append(Problem(cap, pid, "missing-feature",
                                        f"required {missing} but provider declares "
                                        f"{sorted(f for f, v in m.provides.items() if v)}"))
            continue
        found[cap] = Binding(cap, cls, {k: v for k, v in section.items() if k != "provider"}, m)

    for cap, feats in requirements.items():
        if any(feats.values()) and cap not in capabilities:
            res.problems.append(Problem(cap, "-", "dependency",
                                        f"required features {sorted(feats)} but no provider configured"))

    # initialisation order: a provider's `requires` capabilities come first
    ordered: list[Binding] = []
    seen: set[str] = set()
    visiting: set[str] = set()

    def visit(cap: str) -> None:
        if cap in seen:
            return
        if cap in visiting:
            res.problems.append(Problem(cap, found[cap].manifest.id, "dependency", "circular requires"))
            return
        visiting.add(cap)
        for dep in found[cap].manifest.requires:
            if dep not in found:
                if dep not in capabilities:
                    res.problems.append(Problem(cap, found[cap].manifest.id, "dependency",
                                                f"requires capability {dep!r}, which is not configured"))
                continue
            visit(dep)
        visiting.discard(cap)
        seen.add(cap)
        ordered.append(found[cap])

    for cap in found:
        visit(cap)
    res.bindings = ordered
    return res
