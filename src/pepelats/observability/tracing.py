"""OpenTelemetry tracer provider and OTLP span export.

HTTP request spans come from the host's ASGI instrumentation middleware (transport-
agnostic), so this module stays free of any web framework.
"""

import os
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

# Set at configure time from ServiceConfig so the instrumentation scope is never a
# product literal.
_tracer_name = __name__
_tracer_provider: TracerProvider | None = None


def configure_tracing(
    resource: Resource,
    otlp_endpoint: str | None,
    *,
    tracer_name: str,
) -> bool:
    global _tracer_name, _tracer_provider
    _tracer_name = tracer_name

    tracer_provider = TracerProvider(resource=resource)
    if otlp_endpoint:
        tracer_provider.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter(endpoint=f"{otlp_endpoint}/v1/traces"))
        )

    _tracer_provider = tracer_provider
    trace.set_tracer_provider(tracer_provider)
    return otlp_endpoint is not None


def shutdown_tracing() -> None:
    global _tracer_provider
    if _tracer_provider is not None:
        _tracer_provider.shutdown()
        _tracer_provider = None


def resolve_otlp_endpoint(configured: str | None) -> str | None:
    endpoint = configured or os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    if endpoint == "":
        return None
    return endpoint


@contextmanager
def span(name: str) -> Iterator[None]:
    tracer = trace.get_tracer(_tracer_name)
    with tracer.start_as_current_span(name):
        yield


def add_trace_context(
    _logger: object,
    _method_name: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    current_span = trace.get_current_span()
    if not current_span.is_recording():
        return event_dict

    span_context = current_span.get_span_context()
    if span_context.trace_id == 0:
        return event_dict

    event_dict["trace_id"] = format(span_context.trace_id, "032x")
    event_dict["span_id"] = format(span_context.span_id, "016x")
    return event_dict
