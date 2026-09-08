from __future__ import annotations

from dataclasses import dataclass

from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.metrics import Counter, Histogram, Meter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased
from opentelemetry.trace import Tracer


@dataclass(frozen=True, slots=True)
class TelemetryRuntime:
    enabled: bool
    tracer: Tracer
    meter: Meter
    http_requests: Counter
    http_duration_ms: Histogram
    _tracer_provider: TracerProvider | None = None
    _meter_provider: MeterProvider | None = None

    def shutdown(self) -> None:
        if self._meter_provider is not None:
            self._meter_provider.shutdown()
        if self._tracer_provider is not None:
            self._tracer_provider.shutdown()


def configure_telemetry(
    *,
    enabled: bool,
    endpoint: str,
    service_name: str,
    service_version: str,
    environment: str,
    sample_ratio: float,
    export_interval_seconds: int,
) -> TelemetryRuntime:
    if not enabled:
        tracer = trace.get_tracer(service_name, service_version)
        meter = metrics.get_meter(service_name, service_version)
        return TelemetryRuntime(
            enabled=False,
            tracer=tracer,
            meter=meter,
            http_requests=meter.create_counter("auto_video_sub.http.requests"),
            http_duration_ms=meter.create_histogram(
                "auto_video_sub.http.server.duration",
                unit="ms",
            ),
        )

    resource = Resource.create(
        {
            "service.name": service_name,
            "service.version": service_version,
            "deployment.environment.name": environment,
        }
    )
    base_endpoint = endpoint.rstrip("/")
    tracer_provider = TracerProvider(
        resource=resource,
        sampler=ParentBased(TraceIdRatioBased(sample_ratio)),
    )
    tracer_provider.add_span_processor(
        BatchSpanProcessor(
            OTLPSpanExporter(endpoint=f"{base_endpoint}/v1/traces"),
        )
    )
    metric_reader = PeriodicExportingMetricReader(
        OTLPMetricExporter(endpoint=f"{base_endpoint}/v1/metrics"),
        export_interval_millis=export_interval_seconds * 1000,
    )
    meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
    tracer = tracer_provider.get_tracer(service_name, service_version)
    meter = meter_provider.get_meter(service_name, service_version)
    return TelemetryRuntime(
        enabled=True,
        tracer=tracer,
        meter=meter,
        http_requests=meter.create_counter(
            "auto_video_sub.http.requests",
            description="Completed API HTTP requests",
        ),
        http_duration_ms=meter.create_histogram(
            "auto_video_sub.http.server.duration",
            unit="ms",
            description="API HTTP request duration",
        ),
        _tracer_provider=tracer_provider,
        _meter_provider=meter_provider,
    )
