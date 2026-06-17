"""One-shot observability init at host build — brings up all three OTel signals.

Idempotent per process: providers are global. Call shutdown_observability() on host
exit to flush exporters and allow a fresh configure if the process boots again.
"""

import time

from pepelats.observability.logging import (
    configure_logging,
    get_logger,
    shutdown_logging,
)
from pepelats.observability.metrics import configure_metrics, shutdown_metrics
from pepelats.observability.observability_config import ObservabilityConfig
from pepelats.observability.resource import build_resource
from pepelats.observability.tracing import configure_tracing, shutdown_tracing

_configured = False


def configure_observability(config: ObservabilityConfig) -> None:
    global _configured

    if _configured:
        return

    service = config.service
    resource = build_resource(service)
    # enabled is the single switch; the config validator guarantees a non-empty
    # endpoint whenever it is on, so disabled simply means no OTLP export.
    otlp_endpoint = config.otlp_endpoint if config.enabled else None

    # One Resource + one endpoint drive all three signals. Tracing is configured
    # first so the global tracer provider is set before the host builds its ASGI
    # instrumentation middleware (and before any get_tracer call).
    export_timeout = config.export_timeout_seconds
    trace_export = configure_tracing(
        resource,
        otlp_endpoint,
        tracer_name=service.service_name,
        export_timeout_seconds=export_timeout,
    )
    metric_export = configure_metrics(
        resource,
        otlp_endpoint,
        export_timeout_seconds=export_timeout,
    )
    log_export = configure_logging(
        config.logging,
        {
            "service_name": service.service_name,
            "service_version": service.service_version,
            "instance_id": service.instance_id,
        },
        resource=resource,
        otlp_endpoint=otlp_endpoint,
        export_timeout_seconds=export_timeout,
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

    # Synchronous and blocking: each provider's final export runs to completion (or
    # gives up at its per-export timeout) and joins its worker thread. Bracketed with
    # start/complete logs so a slow or failing flush is visible rather than silent;
    # any OTLP export errors surface between the two. After this returns, no exporter
    # thread is left running.
    log = get_logger(__name__)
    log.info("observability_shutdown_started")
    started_at = time.monotonic()

    shutdown_logging()
    shutdown_metrics()
    shutdown_tracing()
    _configured = False

    # OTLP log export is torn down by now; this lands on the console/file sinks.
    log.info(
        "observability_shutdown_complete",
        elapsed_seconds=round(time.monotonic() - started_at, 2),
    )
