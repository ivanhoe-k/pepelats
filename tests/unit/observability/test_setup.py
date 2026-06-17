"""Unit tests for configure_observability wiring (no exporters, no network).

The three signal configurators are patched to record the keyword args they receive,
so we assert the single export-timeout budget reaches all of them.
"""

from typing import Any

import pytest

from pepelats.configuration import ServiceConfig
from pepelats.observability import logging, metrics, setup, tracing
from pepelats.observability.logging_config import LoggingConfig
from pepelats.observability.observability_config import ObservabilityConfig


@pytest.fixture
def observability_config() -> ObservabilityConfig:
    return ObservabilityConfig(
        service=ServiceConfig(
            service_name="test-service",
            service_version="1.0.0",
            instance_id="instance-1",
        ),
        logging=LoggingConfig(log_level="INFO", sinks=["console"]),
        otlp_endpoint=None,
        export_timeout_seconds=3.5,
    )


def test_export_timeout_reaches_every_signal(
    observability_config: ObservabilityConfig,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorded: dict[str, float] = {}

    def record(name: str) -> Any:
        def _configure(*_args: Any, export_timeout_seconds: float, **_kwargs: Any) -> bool:
            recorded[name] = export_timeout_seconds
            return False

        return _configure

    monkeypatch.setattr(setup, "_configured", False)
    monkeypatch.setattr(setup, "configure_tracing", record("tracing"))
    monkeypatch.setattr(setup, "configure_metrics", record("metrics"))
    monkeypatch.setattr(setup, "configure_logging", record("logging"))

    setup.configure_observability(observability_config)

    assert recorded == {"tracing": 3.5, "metrics": 3.5, "logging": 3.5}


def test_providers_do_not_register_atexit_shutdown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The host lifecycle is the sole owner of observability teardown. If OTel also
    # registered an atexit handler, it would re-run shutdown on the main thread at
    # interpreter exit and block on an unreachable collector. A None atexit handle
    # on each provider is the observable effect of shutdown_on_exit=False.
    config = ObservabilityConfig(
        service=ServiceConfig(
            service_name="test-service",
            service_version="1.0.0",
            instance_id="instance-1",
        ),
        logging=LoggingConfig(log_level="INFO", sinks=["console"]),
        # enabled with a dead endpoint so the OTLP log provider is built;
        # export_timeout keeps the autouse teardown flush quick (no collector to reach).
        enabled=True,
        otlp_endpoint="http://localhost:4318",
        export_timeout_seconds=0.1,
    )

    monkeypatch.setattr(setup, "_configured", False)
    setup.configure_observability(config)

    assert tracing._tracer_provider is not None
    assert tracing._tracer_provider._atexit_handler is None
    assert metrics._meter_provider is not None
    assert metrics._meter_provider._atexit_handler is None
    assert logging._logger_provider is not None
    # LoggerProvider names the handle _at_exit_handler (not _atexit_handler).
    assert logging._logger_provider._at_exit_handler is None


def test_shutdown_brackets_flush_with_start_and_complete_logs(
    observability_config: ObservabilityConfig,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The flush must be observable: a start log, then a complete log carrying the
    # elapsed time, so a slow or failing teardown is never silent.
    events: list[str] = []
    monkeypatch.setattr(setup, "shutdown_logging", lambda: events.append("logging"))
    monkeypatch.setattr(setup, "shutdown_metrics", lambda: events.append("metrics"))
    monkeypatch.setattr(setup, "shutdown_tracing", lambda: events.append("tracing"))

    logged: list[tuple[str, dict[str, Any]]] = []

    class RecordingLogger:
        def info(self, event: str, **fields: Any) -> None:
            logged.append((event, fields))

    monkeypatch.setattr(setup, "get_logger", lambda _name: RecordingLogger())
    monkeypatch.setattr(setup, "_configured", True)

    setup.shutdown_observability()

    assert events == ["logging", "metrics", "tracing"]
    assert [event for event, _ in logged] == [
        "observability_shutdown_started",
        "observability_shutdown_complete",
    ]
    assert "elapsed_seconds" in logged[1][1]
