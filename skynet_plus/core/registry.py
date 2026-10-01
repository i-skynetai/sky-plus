"""Where providers are found: explicit registration, plus entry points from installed packages."""
from __future__ import annotations

from collections.abc import Iterable
from importlib import metadata

from .provider import Manifest, Provider

ENTRY_POINT_GROUP = "skynet_plus.providers"


class Registry:
    def __init__(self) -> None:
        self._classes: dict[tuple[str, str], type[Provider]] = {}
        self.load_errors: list[str] = []
        self.skipped: dict[str, str] = {}      # built-in adapters whose library is absent

    def register(self, cls: type[Provider]) -> type[Provider]:
        m = cls.manifest
        self._classes[(m.capability, m.id)] = cls
        return cls

    def register_all(self, classes: Iterable[type[Provider]]) -> None:
        for c in classes:
            self.register(c)

    def discover(self, group: str = ENTRY_POINT_GROUP) -> list[str]:
        """Load every installed provider that advertises itself. Failures are recorded, not raised."""
        loaded: list[str] = []
        for ep in metadata.entry_points(group=group):
            try:
                obj = ep.load()
                classes = obj if isinstance(obj, (list, tuple)) else [obj]
                for c in classes:
                    key = (c.manifest.capability, c.manifest.id)
                    if key in self._classes:
                        self.load_errors.append(
                            f"{ep.name}: refused — {c.manifest.capability}/{c.manifest.id} already exists "
                            f"({self._classes[key].__module__}); a plug-in may not replace a provider")
                        continue
                    self.register(c)
                    loaded.append(c.manifest.ref)
            except Exception as exc:  # noqa: BLE001 — a broken plugin must not break the kernel
                self.load_errors.append(f"{ep.name}: {type(exc).__name__}: {exc}")
        return loaded

    def get(self, capability: str, provider_id: str) -> type[Provider] | None:
        return self._classes.get((capability, provider_id))

    def for_capability(self, capability: str) -> list[Manifest]:
        return [c.manifest for (cap, _), c in sorted(self._classes.items()) if cap == capability]

    def manifests(self) -> list[Manifest]:
        return [c.manifest for _, c in sorted(self._classes.items())]


def default_registry() -> Registry:
    from ..providers import fake, optional_providers, rules
    reg = Registry()
    reg.register_all(fake.ALL)
    reg.register(rules.RulesGuardrail)
    loaded, reg.skipped = optional_providers()
    reg.register_all(loaded)
    reg.discover()
    return reg
