"""Builds console, file, and OTLP log handlers from logging config."""

import logging
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import structlog
from opentelemetry._logs import set_logger_provider
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.resources import Resource

from pepelats.observability.logging_config import (
    ConsoleSinkConfig,
    LoggingConfig,
)

SinkHandlerFactory = Callable[[int, LoggingConfig, list[Any]], logging.Handler]

_sink_factories: dict[str, SinkHandlerFactory] = {}


def register_sink(name: str, factory: SinkHandlerFactory) -> None:
    """Register a log sink under a config name. The seam for apps/integrations to add
    sinks (e.g. Sentry, Loki) without editing core."""
    _sink_factories[name] = factory


def attach_sinks(
    root_logger: logging.Logger,
    level: int,
    config: LoggingConfig,
    foreign_pre_chain: list[Any],
) -> None:
    for sink in config.sinks:
        factory = _sink_factories.get(sink)
        if factory is None:
            msg = f"unknown logging sink: {sink!r}"
            raise ValueError(msg)
        root_logger.addHandler(factory(level, config, foreign_pre_chain))


def build_otlp_log_handler(
    resource: Resource,
    otlp_endpoint: str,
    level: int,
    foreign_pre_chain: list[Any],
    *,
    export_timeout_seconds: float,
) -> tuple[logging.Handler, LoggerProvider]:
    # The OTLP logs signal: a LoggerProvider exports structured records over OTLP.
    # Keyed off the same endpoint as traces and metrics.
    # shutdown_on_exit=False: the host lifecycle owns teardown; see tracing.py.
    provider = LoggerProvider(resource=resource, shutdown_on_exit=False)
    provider.add_log_record_processor(
        BatchLogRecordProcessor(
            OTLPLogExporter(
                endpoint=f"{otlp_endpoint}/v1/logs",
                timeout=export_timeout_seconds,
            )
        )
    )
    set_logger_provider(provider)

    handler = LoggingHandler(level=level, logger_provider=provider)
    handler.setFormatter(_file_formatter(foreign_pre_chain))
    return handler, provider


def _build_console_handler(
    level: int,
    config: LoggingConfig,
    foreign_pre_chain: list[Any],
) -> logging.Handler:
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    handler.setFormatter(_console_formatter(config.console, foreign_pre_chain))
    return handler


def _build_file_handler(
    level: int,
    config: LoggingConfig,
    foreign_pre_chain: list[Any],
) -> logging.Handler:
    log_dir = Path(config.file.dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    handler = logging.FileHandler(log_dir / config.file.file_name, encoding="utf-8")
    handler.setLevel(level)
    handler.setFormatter(_file_formatter(foreign_pre_chain))
    return handler


def _console_formatter(
    config: ConsoleSinkConfig,
    foreign_pre_chain: list[Any],
) -> structlog.stdlib.ProcessorFormatter:
    processor: Any = (
        structlog.processors.JSONRenderer()
        if config.json_logs
        else structlog.dev.ConsoleRenderer(colors=True)
    )
    return structlog.stdlib.ProcessorFormatter(
        processor=processor,
        foreign_pre_chain=foreign_pre_chain,
    )


def _file_formatter(
    foreign_pre_chain: list[Any],
) -> structlog.stdlib.ProcessorFormatter:
    return structlog.stdlib.ProcessorFormatter(
        processor=structlog.processors.JSONRenderer(),
        foreign_pre_chain=foreign_pre_chain,
    )


register_sink("console", _build_console_handler)
register_sink("file", _build_file_handler)
