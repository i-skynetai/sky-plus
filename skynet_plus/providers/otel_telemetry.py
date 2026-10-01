"""OpenTelemetry telemetry provider (SP-033).

One span per run and, through the kernel's tracing of every provider call, a child span
per model, memory, decision, guardrail and tool call, each tagged with the provider and
its version. Exporters: `console`, `otlp` (the standard endpoint variables apply), and
`memory` for tests. The global tracer provider is left alone unless `set_global: true`.
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Any, Iterator

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter, SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from ..core.provider import Health, Manifest
from ..spi import TelemetryProvider

VERSION = "0.2.0"


def _attr(value: Any) -> Any:
    return value if isinstance(value, (str, bool, int, float)) else str(value)


class OpenTelemetryTelemetry(TelemetryProvider):
    manifest = Manifest(id="opentelemetry", capability="telemetry", version=VERSION,
                        provides={"spans": True, "events": True, "otlp": True}, package="otel",
                        description="OpenTelemetry spans and events; console, OTLP or in-memory export")

    def __init__(self, config: dict | None = None) -> None:
        super().__init__(config)
        default = "otlp" if os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT") else "console"
        self.exporter_name: str = str(self.config.get("exporter", default))
        self.service_name: str = str(self.config.get("service_name", "skynet-plus"))
        self.exporter: Any = None
        self._provider: TracerProvider | None = None
        self._tracer: Any = None

    async def initialize(self) -> None:
        resource = Resource.create({"service.name": self.service_name, "skynet.version": VERSION})
        provider = TracerProvider(resource=resource)
        if self.exporter_name == "memory":
            self.exporter = InMemorySpanExporter()
            provider.add_span_processor(SimpleSpanProcessor(self.exporter))
        elif self.exporter_name == "otlp":
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter  # optional dep
            self.exporter = OTLPSpanExporter(endpoint=self.config.get("endpoint"))
            provider.add_span_processor(BatchSpanProcessor(self.exporter))
        elif self.exporter_name == "none":
            self.exporter = None
        else:
            self.exporter = ConsoleSpanExporter()
            provider.add_span_processor(SimpleSpanProcessor(self.exporter))
        if self.config.get("set_global"):
            trace.set_tracer_provider(provider)
        self._provider = provider
        self._tracer = provider.get_tracer("skynet_plus", VERSION)

    async def health(self) -> Health:
        if self._tracer is None:
            return Health(ok=False, detail="not initialised")
        return Health(ok=True, detail=f"exporter {self.exporter_name}; service {self.service_name}")

    @contextmanager
    def span(self, name: str, attributes: dict | None = None) -> Iterator[Any]:
        if self._tracer is None:
            yield None
            return
        with self._tracer.start_as_current_span(name) as span:
            for k, v in (attributes or {}).items():
                span.set_attribute(k, _attr(v))
            yield span

    async def emit(self, kind: str, **data: Any) -> None:
        current = trace.get_current_span()
        attrs = {k: _attr(v) for k, v in data.items()}
        if current is not None and current.get_span_context().is_valid:
            current.add_event(kind, attrs)
        elif self._tracer is not None:
            with self._tracer.start_as_current_span(kind) as span:
                for k, v in attrs.items():
                    span.set_attribute(k, v)

    def finished_spans(self) -> list:
        """The spans an in-memory exporter has collected (tests)."""
        return list(self.exporter.get_finished_spans()) if isinstance(self.exporter, InMemorySpanExporter) else []

    async def close(self) -> None:
        if self._provider is not None:
            try:
                self._provider.force_flush()
                self._provider.shutdown()
            except Exception:  # noqa: BLE001
                pass
        self._provider = self._tracer = None
