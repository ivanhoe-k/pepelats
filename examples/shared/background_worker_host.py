"""Background worker host — importable from tests and the background-worker example."""

from __future__ import annotations

import asyncio
from pathlib import Path

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from pepelats.configuration import Configuration
from pepelats.dependency_injection import ServiceCollection
from pepelats.hosting import HostPipeline, WebHostBuilder, request_services
from pepelats.hosting.background_service import BackgroundService
from pepelats.hosting.web_host import WebHost


class TickWorker(BackgroundService):
    def __init__(self) -> None:
        self.ticks = 0

    async def execute_async(self, stopping: asyncio.Event) -> None:
        while not stopping.is_set():
            self.ticks += 1
            try:
                await asyncio.wait_for(stopping.wait(), timeout=1.0)
            except TimeoutError:
                continue


class WorkerStatus:
    def __init__(self, worker: TickWorker) -> None:
        self._worker = worker

    def snapshot(self) -> dict[str, int]:
        return {"ticks": self._worker.ticks}


def register(services: ServiceCollection, configuration: Configuration) -> None:
    services.add_singleton(TickWorker)
    services.add_hosted_service(TickWorker)
    services.add_singleton(WorkerStatus)


async def status(request: Request) -> JSONResponse:
    worker_status = await request_services(request).get(WorkerStatus)
    return JSONResponse(worker_status.snapshot())


def _configure_pipeline(pipeline: HostPipeline) -> None:
    pipeline.map(Route("/status", status))


def build_host(config_dir: Path) -> WebHost:
    return (
        WebHostBuilder.create(config_dir=config_dir)
        .configure_services(register)
        .configure_pipeline(_configure_pipeline)
        .build()
    )
