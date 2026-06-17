"""One-shot observability init at host build — brings up all three OTel signals.

Idempotent per process: providers are global. Call shutdown_observability() on host
exit to flush exporters and allow a fresh configure if the process boots again.
"""

from pepelats.observability.logging import (
    configure_logging,
    get_logger,
    shutdown_logging,
)
from pepelats.observability.metrics import configure_metrics, shutdown_metrics
from pepelats.observability.observability_config import ObservabilityConfig
from pepelats.observability.resource import build_resource
from pepelats.observability.tracing import (
    configure_tracing,
    resolve_otlp_endpoint,
    shutdown_tracing,
)

_configured = False


def configure_observability(config: ObservabilityConfig) -> None:
    global _configured

    if _configured:
        return

    service = config.service
    resource = build_resource(service)
    otlp_endpoint = resolve_otlp_endpoint(config.otlp_endpoint)

    # One Resource + one endpoint drive all three signals. Tracing is configured
    # first so the global tracer provider is set before the host builds its ASGI
    # instrumentation middleware (and before any get_tracer call).
    trace_export = configure_tracing(
        resource,
        otlp_endpoint,
        tracer_name=service.service_name,
    )
    metric_export = configure_metrics(resource, otlp_endpoint)
    log_export = configure_logging(
        config.logging,
        {
            "service_name": service.service_name,
            "service_version": service.service_version,
            "instance_id": service.instance_id,
        },
        resource=resource,
        otlp_endpoint=otlp_endpoint,
    )

    _configured = True
    get_logger(__name__).info(
        "observability_configured",
        log_level=config.logging.log_level,
        sinks=config.logging.sinks,
        otlp_export_configured=otlp_endpoint is not None,
        otlp_trace_export=trace_export,
        otlp_metric_export=metric_export,
        otlp_log_export=log_export,
    )


def shutdown_observability() -> None:
    global _configured

    if not _configured:
        return

    shutdown_logging()
    shutdown_metrics()
    shutdown_tracing()
    _configured = False
