"""Integration tests for WebHostBuilder wiring: lifespan ordering and failure cleanup."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
from starlette.applications import Starlette
from starlette.testclient import TestClient

from pepelats.configuration import Configuration
from pepelats.dependency_injection import ServiceCollection
from pepelats.hosting import WebHostBuilder, web_host_builder
from pepelats.hosting.background_service import BackgroundService


class OrderingWorker(BackgroundService):
    events: list[str] = []

    async def execute_async(self, stopping: asyncio.Event) -> None:
        OrderingWorker.events.append("service_started")
        await stopping.wait()
        OrderingWorker.events.append("service_stopped")


def _register_worker(services: ServiceCollection, configuration: Configuration) -> None:
    services.add_hosted_service(OrderingWorker)


def test_app_lifespan_runs_inside_hosted_services_window(config_dir: Path) -> None:
    OrderingWorker.events = []
    events = OrderingWorker.events

    @asynccontextmanager
    async def app_lifespan(_: Starlette) -> AsyncIterator[None]:
        events.append("app_startup")
        try:
            yield
        finally:
            events.append("app_shutdown")

    host = (
        WebHostBuilder.create(config_dir=config_dir)
        .configure_services(_register_worker)
        .configure_lifespan(app_lifespan)
        .build()
    )

    with TestClient(host.app):
        pass

    # The app lifespan runs while the hosted service is up, and hosted services are
    # torn down only after the app lifespan has exited (the "inside the window"
    # contract). Startup interleaving of the two is left to the event loop, so only
    # the ordering relative to teardown is asserted.
    assert events.index("service_started") < events.index("app_shutdown")
    assert events.index("app_shutdown") < events.index("service_stopped")


def test_build_cleans_up_observability_on_failure(
    config_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    shutdown_calls: list[str] = []
    monkeypatch.setattr(
        web_host_builder,
        "shutdown_observability",
        lambda: shutdown_calls.append("shutdown"),
    )

    def failing(services: ServiceCollection, configuration: Configuration) -> None:
        raise RuntimeError("configurator failed")

    builder = WebHostBuilder.create(config_dir=config_dir).configure_services(failing)

    with pytest.raises(RuntimeError, match="configurator failed"):
        builder.build()

    assert shutdown_calls == ["shutdown"]
