"""Framework smoke tests for the FastAPI host (FastAPIHostBuilder + InjectRoute).

Mirrors the generic-host smoke set on the Web API layer: same registrations resolve via
`Inject[T]`, and the InjectRoute is exercised both with and without an explicit Request
parameter (its two container-resolution branches).
"""

import asyncio
from pathlib import Path

import pytest
from fastapi import APIRouter, FastAPI, Request
from starlette.testclient import TestClient

from pepelats.configuration import Configuration
from pepelats.dependency_injection import Inject, ServiceCollection
from pepelats.hosting.background_service import BackgroundService
from pepelats.hosting.web_host import WebHost
from pepelats.integrations.fastapi import FastAPIHostBuilder, InjectRoute

pytestmark = pytest.mark.smoke


class Probe:
    message = "fastapi-ok"


class SmokeWorker(BackgroundService):
    events: list[str] = []

    async def execute_async(self, stopping: asyncio.Event) -> None:
        SmokeWorker.events.append("started")
        await stopping.wait()
        SmokeWorker.events.append("stopped")


router = APIRouter(route_class=InjectRoute)


@router.get("/probe")
async def probe(probe: Inject[Probe]) -> dict[str, str]:
    return {"message": probe.message}


@router.get("/probe-with-request")
async def probe_with_request(request: Request, probe: Inject[Probe]) -> dict[str, str]:
    return {"message": probe.message, "path": request.url.path}


@router.get("/boom")
async def boom(_: Inject[Probe]) -> dict[str, str]:
    raise RuntimeError("boom")


def _register_services(
    services: ServiceCollection, configuration: Configuration
) -> None:
    services.add_singleton(Probe)
    services.add_hosted_service(SmokeWorker)


def _include_router(app: FastAPI) -> None:
    app.include_router(router)


def _build_host(config_dir: Path) -> WebHost:
    return (
        FastAPIHostBuilder.create(config_dir=config_dir)
        .configure_services(_register_services)
        .configure_api(_include_router)
        .build()
    )


def test_boots_serves_injects_and_runs_hosted_service(config_dir: Path) -> None:
    SmokeWorker.events = []
    host = _build_host(config_dir)

    with TestClient(host.app) as client:
        response = client.get("/probe")

    assert response.status_code == 200
    assert response.json() == {"message": "fastapi-ok"}
    assert SmokeWorker.events == ["started", "stopped"]


def test_inject_resolves_with_explicit_request_param(config_dir: Path) -> None:
    host = _build_host(config_dir)

    with TestClient(host.app) as client:
        response = client.get("/probe-with-request")

    assert response.status_code == 200
    assert response.json() == {
        "message": "fastapi-ok",
        "path": "/probe-with-request",
    }


def test_openapi_uses_service_identity(config_dir: Path) -> None:
    host = _build_host(config_dir)

    with TestClient(host.app) as client:
        info = client.get("/openapi.json").json()["info"]

    assert info["title"] == "test-service"
    assert info["version"] == "1.0.0"


def test_injected_params_absent_from_openapi(config_dir: Path) -> None:
    host = _build_host(config_dir)

    with TestClient(host.app) as client:
        paths = client.get("/openapi.json").json()["paths"]

    # Inject[Probe] (and the explicit Request) must not surface as request parameters.
    assert "parameters" not in paths["/probe"]["get"]
    assert "parameters" not in paths["/probe-with-request"]["get"]


def test_unhandled_error_yields_500_and_host_survives(config_dir: Path) -> None:
    host = _build_host(config_dir)

    with TestClient(host.app, raise_server_exceptions=False) as client:
        errored = client.get("/boom")
        recovered = client.get("/probe")

    assert errored.status_code == 500
    assert recovered.status_code == 200
