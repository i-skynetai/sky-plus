"""The kernel: load config → resolve providers → initialise in order → health → services."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .. import __version__ as API_VERSION
from .config import Config, load as load_config
from .contracts import Task
from .errors import ProviderError, ResolutionError
from .events import EventBus
from .provider import CAPABILITIES, Provider
from .registry import Registry, default_registry
from .resolver import Resolution, resolve
from .runrecord import Recorder, new_record


TRACED_METHODS = frozenset({"complete", "remember", "recall", "forget", "decide", "check", "evaluate",
                            "authorize", "start", "signal", "status", "search", "find_symbols",
                            "read_source", "pay", "run"})


class Traced:
    """A provider whose port methods run inside a telemetry span. Everything else passes through."""

    def __init__(self, provider: Provider, telemetry: Any, capability: str) -> None:
        self._provider, self._telemetry, self._capability = provider, telemetry, capability

    def __getattr__(self, name: str) -> Any:
        attr = getattr(self._provider, name)
        if name in TRACED_METHODS and callable(attr):
            manifest = self._provider.manifest

            async def traced(*args: Any, **kwargs: Any) -> Any:
                with self._telemetry.span(f"{self._capability}.{name}",
                                          {"provider": manifest.id, "version": manifest.version}):
                    return await attr(*args, **kwargs)
            return traced
        return attr

    @property
    def manifest(self):
        return self._provider.manifest

    def __repr__(self) -> str:
        return f"<Traced {self._provider!r}>"


class Services:
    """The initialised providers, by capability. `services.model`, `services.get("memory")`."""

    def __init__(self, providers: dict[str, Provider]) -> None:
        self._providers = providers

    def get(self, capability: str) -> Provider | None:
        return self._providers.get(capability)

    def has(self, capability: str) -> bool:
        return capability in self._providers

    def require(self, capability: str) -> Provider:
        try:
            return self._providers[capability]
        except KeyError:
            raise ProviderError(f"no provider configured for {capability!r}") from None

    def __getattr__(self, name: str) -> Provider:
        cap = name.replace("_", "-")
        if cap in self._providers:
            return self._providers[cap]
        raise AttributeError(f"no service {name!r} (configured: {sorted(self._providers)})")

    def refs(self) -> dict[str, str]:
        return {cap: p.manifest.ref for cap, p in self._providers.items()}

    def __iter__(self):
        return iter(self._providers.items())


@dataclass
class DoctorRow:
    capability: str
    provider: str
    status: str          # OK | DEGRADED | MISSING | INCOMPATIBLE | UNSATISFIED | ERROR | UNCONFIGURED
    detail: str = ""


@dataclass
class DoctorReport:
    profile: str
    rows: list[DoctorRow] = field(default_factory=list)
    registry_errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(r.status in ("OK", "UNCONFIGURED") for r in self.rows)

    def render(self) -> str:
        width = max(len(r.capability) for r in self.rows) if self.rows else 12
        lines = [f"profile: {self.profile}", ""]
        for r in self.rows:
            lines.append(f"  {r.capability:<{width}}  {r.status:<12} {r.provider:<24} {r.detail}")
        if self.registry_errors:
            lines += ["", "plugins that failed to load:"] + [f"  - {e}" for e in self.registry_errors]
        lines += ["", "verdict: " + ("OK — every configured provider is healthy" if self.ok
                                     else "NOT READY — fix the rows above")]
        return "\n".join(lines)


class Kernel:
    def __init__(self, config: Config, registry: Registry | None = None) -> None:
        self.config = config
        self.registry = registry or default_registry()
        self.events = EventBus()
        self.services = Services({})
        self._started = False

    @classmethod
    def load(cls, path: str | Path | None = None, profile: str | None = None,
             overrides: dict | None = None, requirements: dict | None = None,
             registry: Registry | None = None) -> "Kernel":
        return cls(load_config(path, profile=profile, overrides=overrides, requirements=requirements),
                   registry=registry)

    # -- resolution -------------------------------------------------------------------
    def resolve(self, requirements: dict | None = None) -> Resolution:
        reqs = {cap: dict(f) for cap, f in self.config.requirements.items()}
        for cap, feats in (requirements or {}).items():
            reqs.setdefault(cap, {}).update(feats)
        return resolve(self.registry, self.config.capabilities, reqs, API_VERSION)

    # -- lifecycle --------------------------------------------------------------------
    def unmet(self, requirements: dict | None) -> list[str]:
        """Features a *running* kernel's providers do not declare, as problem strings."""
        problems = []
        for cap, feats in (requirements or {}).items():
            provider = self.services.get(cap)
            if provider is None:
                if any(feats.values()):
                    problems.append(f"{cap}/-: dependency: required features {sorted(feats)} but no provider is running")
                continue
            missing = provider.manifest.missing(feats)
            if missing:
                problems.append(f"{cap}/{provider.manifest.id}: missing-feature: required {missing} "
                                f"but the running provider declares "
                                f"{sorted(f for f, v in provider.manifest.provides.items() if v)}")
        return problems

    async def start(self, requirements: dict | None = None) -> "Kernel":
        if self._started:
            unmet = self.unmet(requirements)
            if unmet:
                raise ResolutionError(unmet)
            return self
        resolution = self.resolve(requirements)
        if not resolution.ok:
            raise ResolutionError(resolution.problems)
        providers: dict[str, Provider] = {}
        try:
            for b in resolution.bindings:
                instance = b.provider_cls(b.config)
                try:
                    await instance.initialize()
                    health = await instance.health()
                except Exception as exc:  # noqa: BLE001
                    raise ProviderError(f"{b.capability}/{b.manifest.ref} failed to start: {exc}") from exc
                if not health.ok:
                    raise ProviderError(f"{b.capability}/{b.manifest.ref} unhealthy: {health.detail}")
                providers[b.capability] = instance
                self.events.emit("provider.started", capability=b.capability, provider=b.manifest.ref)
        except Exception:
            for p in reversed(list(providers.values())):
                try:
                    await p.close()
                except Exception:  # noqa: BLE001
                    pass
            raise
        telemetry = providers.get("telemetry")
        if telemetry is not None:
            providers = {cap: (p if cap == "telemetry" else Traced(p, telemetry, cap)) for cap, p in providers.items()}
        self.services = Services(providers)
        self._started = True
        self.events.emit("kernel.started", providers=self.services.refs())
        return self

    async def stop(self) -> None:
        for _, p in reversed(list(self.services)):
            try:
                await (p._provider.close() if isinstance(p, Traced) else p.close())
            except Exception:  # noqa: BLE001
                pass
        self.services = Services({})
        self._started = False
        self.events.emit("kernel.stopped")

    async def __aenter__(self) -> "Kernel":
        return await self.start()

    async def __aexit__(self, *exc: Any) -> None:
        await self.stop()

    # -- doctor -----------------------------------------------------------------------
    async def doctor(self, requirements: dict | None = None) -> DoctorReport:
        """Report every capability without leaving anything running. Never raises."""
        report = DoctorReport(profile=self.config.profile, registry_errors=list(self.registry.load_errors))
        try:
            resolution = self.resolve(requirements)
        except Exception as exc:  # noqa: BLE001 — doctor reports, it does not raise
            report.rows.append(DoctorRow("config", "-", "ERROR", f"{type(exc).__name__}: {exc}"))
            return report
        by_cap: dict[str, Any] = {}
        for p in resolution.problems:
            by_cap.setdefault(p.capability, p)   # the first problem for a capability is the one shown
        status_of = {"missing-provider": "MISSING", "incompatible": "INCOMPATIBLE",
                     "missing-feature": "UNSATISFIED", "dependency": "UNSATISFIED"}
        for cap in by_cap:                        # a problem on something outside the taxonomy still shows
            if cap not in CAPABILITIES:
                report.rows.append(DoctorRow(cap, by_cap[cap].provider, "UNSATISFIED", by_cap[cap].detail))
        for cap in CAPABILITIES:
            pid = self.config.provider_id(cap)
            if cap in by_cap:
                p = by_cap[cap]
                report.rows.append(DoctorRow(cap, p.provider, status_of[p.kind], p.detail))
            elif pid is None:
                report.rows.append(DoctorRow(cap, "-", "UNCONFIGURED", "not part of this profile"))
            else:
                b = resolution.binding(cap)
                if b is None:
                    report.rows.append(DoctorRow(cap, pid, "ERROR", "resolved but unbound"))
                    continue
                instance = b.provider_cls(b.config)
                try:
                    await instance.initialize()
                    health = await instance.health()
                    status = "OK" if health.ok else "DEGRADED"
                    detail = health.detail
                except Exception as exc:  # noqa: BLE001
                    status, detail = "ERROR", f"{type(exc).__name__}: {exc}"
                finally:
                    try:
                        await instance.close()
                    except Exception:  # noqa: BLE001
                        pass
                report.rows.append(DoctorRow(cap, b.manifest.ref, status, detail))
        return report

    # -- run records ------------------------------------------------------------------
    def recorder(self, agent: str, task: Task) -> Recorder:
        path = Path(self.config.run_log) if self.config.run_log else None
        return Recorder(new_record(agent, task, self.config.profile, self.services.refs()), path)
