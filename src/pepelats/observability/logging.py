"""Structlog setup with service context and trace ids on every log line.

Structured logging is the log *style* over the OTel logs signal: when an OTLP
endpoint is set, records are also exported via a LoggerProvider (see sinks).
"""

import logging
from collections.abc import Callable
from typing import Any

import structlog
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk.resources import Resource
from structlog.stdlib import BoundLogger

from pepelats.observability.logging_config import LoggingConfig
from pepelats.observability.sinks import attach_sinks, build_otlp_log_handler
from pepelats.observability.tracing import add_trace_context

Processor = Callable[[Any, str, dict[str, Any]], dict[str, Any]]

_logger_provider: LoggerProvider | None = None


def configure_logging(
    config: LoggingConfig,
    service_context: dict[str, str],
    *,
    resource: Resource,
    otlp_endpoint: str | None,
    export_timeout_seconds: float,
) -> bool:
    numeric_level = getattr(logging, config.log_level)
    shared_processors = _shared_processors(service_context)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(numeric_level)

    # foreign_pre_chain runs on stdlib records (asyncio, uvicorn) where structlog
    # passes logger=None; filter_by_level dereferences the logger, so it must not
    # run here. Level filtering for those records is handled by the handler level.
    attach_sinks(root_logger, numeric_level, config, shared_processors)

    otlp_logs_enabled = False
    if otlp_endpoint:
        global _logger_provider
        handler, _logger_provider = build_otlp_log_handler(
            resource,
            otlp_endpoint,
            numeric_level,
            shared_processors,
            export_timeout_seconds=export_timeout_seconds,
        )
        root_logger.addHandler(handler)
        otlp_logs_enabled = True

    LoggingInstrumentor().instrument(set_logging_format=True)

    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        context_class=dict,
        cache_logger_on_first_use=True,
    )

    _apply_logger_overrides(config.overrides)

    return otlp_logs_enabled


def shutdown_logging() -> None:
    global _logger_provider
    LoggingInstrumentor().uninstrument()
    if _logger_provider is not None:
        _logger_provider.shutdown()
        _logger_provider = None


def get_logger(name: str) -> BoundLogger:
    return structlog.get_logger(name)  # type: ignore[no-any-return]


def _shared_processors(service_context: dict[str, str]) -> list[Any]:
    return [
        _service_context_processor(service_context),
        add_trace_context,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]


def _apply_logger_overrides(overrides: dict[str, str]) -> None:
    for name, level_name in overrides.items():
        logging.getLogger(name).setLevel(getattr(logging, level_name.upper()))


def _service_context_processor(context: dict[str, str]) -> Processor:
    def add_service_context(
        _logger: object,
        _method_name: str,
        event_dict: dict[str, Any],
    ) -> dict[str, Any]:
        event_dict.update(context)
        return event_dict

    return add_service_context
