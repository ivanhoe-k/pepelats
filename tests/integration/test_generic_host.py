"""Framework smoke tests for the generic web host (WebHostBuilder, no FastAPI).

One real host built from synthetic services/routes, driven through TestClient whose
context manager runs the lifespan: build -> configure observability -> start hosted
services -> serve -> resolve DI -> shut down.
"""

import asyncio
from pathlib import Path

import pytest
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from pepelats.configuration import Configuration
from pepelats.dependency_injection import ServiceCollection
from pepelats.hosting import HostPipeline, WebHostBuilder, request_services
from pepelats.hosting.background_service import BackgroundService
from pepelats.hosting.web_host import WebHost

pytestmark = pytest.mark.smoke


class Probe:
    message = "generic-ok"


class SmokeWorker(BackgroundService):
    events: list[str] = []

    async def execute_async(self, stopping: asyncio.Event) -> None:
        SmokeWorker.events.append("started")
        await stopping.wait()
        SmokeWorker.events.append("stopped")


async def _probe(request: Request) -> JSONResponse:
    probe = await request_services(request).get(Probe)
    return JSONResponse({"message": probe.message})


async def _boom(_: Request) -> JSONResponse:
    raise RuntimeError("boom")


def _register_services(
    services: ServiceCollection, configuration: Configuration
) -> None:
    services.add_singleton(Probe)
    services.add_hosted_service(SmokeWorker)


def _register_pipeline(pipeline: HostPipeline) -> None:
    pipeline.map(Route("/probe", _probe))
    pipeline.map(Route("/boom", _boom))


def _build_host(config_dir: Path) -> WebHost:
    return (
        WebHostBuilder.create(config_dir=config_dir)
        .configure_services(_register_services)
        .configure_pipeline(_register_pipeline)
        .build()
    )


def test_boots_serves_injects_and_runs_hosted_service(config_dir: Path) -> None:
    SmokeWorker.events = []
    host = _build_host(config_dir)

    with TestClient(host.app) as client:
        response = client.get("/probe")

    assert response.status_code == 200
    assert response.json() == {"message": "generic-ok"}
    assert SmokeWorker.events == ["started", "stopped"]


def test_unhandled_error_yields_500_and_host_survives(config_dir: Path) -> None:
    SmokeWorker.events = []
    host = _build_host(config_dir)

    with TestClient(host.app, raise_server_exceptions=False) as client:
        errored = client.get("/boom")
        recovered = client.get("/probe")

    assert errored.status_code == 500
    assert recovered.status_code == 200
