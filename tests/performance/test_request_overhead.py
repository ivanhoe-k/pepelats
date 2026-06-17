"""Per-request overhead benchmark — a reference, not a gate.

Measures the framework's added cost on a single endpoint by comparing a bare Starlette
route against the same route served through `WebHostBuilder`. Both run in-process via
TestClient (no uvicorn, no sockets), so the harness overhead is common to both and the
*delta* isolates pepelats's per-request cost: the built-in middleware stack
(OTel ASGI instrumentation, exception logging, request scope) plus resolving a realistic
per-request object graph.

The handler resolves a small but representative graph rather than a single leaf service:
a scoped use case that pulls in a scoped repository (→ singleton database), a singleton
settings, and the host-context `ServiceConfig`, plus a transient clock. This exercises
scoped construction, singleton reuse, host-context injection, and transient creation in
one request — closer to a real handler than a single resolve.

In-process numbers measure framework overhead, not absolute production throughput.
Run with `pytest -m perf`; save/compare baselines with
`pytest -m perf --benchmark-autosave` / `--benchmark-compare`.
"""

from pathlib import Path

import pytest
from pytest_benchmark.fixture import BenchmarkFixture
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from pepelats.configuration import Configuration, ServiceConfig
from pepelats.dependency_injection import ServiceCollection
from pepelats.hosting import HostPipeline, WebHostBuilder, request_services


class Settings:
    pass


class Database:
    pass


class Repository:
    def __init__(self, database: Database) -> None:
        self.database = database


class Clock:
    pass


class HealthUseCase:
    def __init__(
        self,
        repository: Repository,
        settings: Settings,
        service_config: ServiceConfig,
    ) -> None:
        self.repository = repository
        self.settings = settings
        self.service_config = service_config


pytestmark = [pytest.mark.perf, pytest.mark.benchmark(group="GET /probe")]


async def _bare_probe(_: Request) -> JSONResponse:
    return JSONResponse({"message": "ok"})


async def _scoped_probe(request: Request) -> JSONResponse:
    services = request_services(request)
    use_case = await services.get(HealthUseCase)
    await services.get(Clock)
    return JSONResponse({"message": use_case.service_config.service_name})


def _register_services(
    services: ServiceCollection, configuration: Configuration
) -> None:
    services.add_singleton(Settings)
    services.add_singleton(Database)
    services.add_scoped(Repository)
    services.add_transient(Clock)
    services.add_scoped(HealthUseCase)


def _register_pipeline(pipeline: HostPipeline) -> None:
    pipeline.map(Route("/probe", _scoped_probe))


def test_bare_starlette_baseline(benchmark: BenchmarkFixture) -> None:
    app = Starlette(routes=[Route("/probe", _bare_probe)])

    with TestClient(app) as client:
        response = benchmark(lambda: client.get("/probe"))

    assert response.status_code == 200


def test_web_host_request_overhead(
    benchmark: BenchmarkFixture, config_dir: Path
) -> None:
    host = (
        WebHostBuilder.create(config_dir=config_dir)
        .configure_services(_register_services)
        .configure_pipeline(_register_pipeline)
        .build()
    )

    with TestClient(host.app) as client:
        response = benchmark(lambda: client.get("/probe"))

    assert response.status_code == 200
