"""OpenTelemetry meter provider and OTLP metric export."""

from opentelemetry import metrics
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.metrics import Meter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource

_meter_provider: MeterProvider | None = None


def configure_metrics(resource: Resource, otlp_endpoint: str | None) -> bool:
    global _meter_provider

    readers: list[PeriodicExportingMetricReader] = []
    if otlp_endpoint:
        readers.append(
            PeriodicExportingMetricReader(
                OTLPMetricExporter(endpoint=f"{otlp_endpoint}/v1/metrics")
            )
        )

    provider = MeterProvider(resource=resource, metric_readers=readers)
    _meter_provider = provider
    metrics.set_meter_provider(provider)
    return otlp_endpoint is not None


def shutdown_metrics() -> None:
    global _meter_provider
    if _meter_provider is not None:
        _meter_provider.shutdown()
        _meter_provider = None


def get_meter(name: str) -> Meter:
    return metrics.get_meter(name)
