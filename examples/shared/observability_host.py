"""Observability demo host — importable from tests and the observability example."""

from pathlib import Path

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from pepelats.hosting import WebHostBuilder, request_services
from pepelats.hosting.web_host import WebHost
from pepelats.observability import get_logger, span

logger = get_logger(__name__)

async def hello(request: Request) -> JSONResponse:
    _ = request_services(request)
    with span("hello.handle"):
        logger.info("hello.request", path=str(request.url.path))
    return JSONResponse({"status": "ok"})


def build_host(config_dir: Path) -> WebHost:
    return (
        WebHostBuilder.create(config_dir=config_dir)
        .configure_pipeline(lambda pipeline: pipeline.map(Route("/hello", hello)))
        .build()
    )
