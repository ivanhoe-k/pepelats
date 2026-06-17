"""OpenTelemetry tracer provider and OTLP span export.

HTTP request spans come from the host's ASGI instrumentation middleware (transport-
agnostic), so this module stays free of any web framework.
"""

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
    export_timeout_seconds: float,
) -> bool:
    global _tracer_name, _tracer_provider
    _tracer_name = tracer_name

    # shutdown_on_exit=False: the host lifecycle owns teardown. Without this OTel
    # also registers an atexit handler that re-runs shutdown on the main thread at
    # interpreter exit — re-blocking on an unreachable collector after the host has
    # already bounded and abandoned the flush.
    tracer_provider = TracerProvider(resource=resource, shutdown_on_exit=False)
    if otlp_endpoint:
        tracer_provider.add_span_processor(
            BatchSpanProcessor(
                OTLPSpanExporter(
                    endpoint=f"{otlp_endpoint}/v1/traces",
                    timeout=export_timeout_seconds,
                )
            )
        )

    _tracer_provider = tracer_provider
    trace.set_tracer_provider(tracer_provider)
    return otlp_endpoint is not None


def shutdown_tracing() -> None:
    global _tracer_provider
    if _tracer_provider is not None:
        _tracer_provider.shutdown()
        _tracer_provider = None


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
