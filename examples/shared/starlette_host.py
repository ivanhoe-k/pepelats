"""Starlette greeting host — importable from tests and the starlette-basic example."""

from pathlib import Path

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from examples.shared.greeting import (
    Greeter,
    GreetingConfig,
    Repository,
    RequestCounter,
    User,
    register,
)
from pepelats.hosting import WebHostBuilder, request_services
from pepelats.hosting.web_host import WebHost
from pepelats.observability import get_logger, span

logger = get_logger(__name__)


async def greet(request: Request) -> JSONResponse:
    name = request.path_params["name"]
    services = request_services(request)

    greeter = await services.get(Greeter)  # type: ignore[type-abstract]
    counter = await services.get(RequestCounter)
    config = await services.get(GreetingConfig)
    users = await services.get(Repository[User, int])

    message = greeter.greet(name)
    if config.shout:
        message = message.upper()
    message += config.punctuation
    count = counter.increment()

    with span("greet.handle"):
        logger.info("greeted", name=name, count=count, known_users=users.count())

    return JSONResponse({"message": message, "count": count})


def build_host(config_dir: Path) -> WebHost:
    return (
        WebHostBuilder.create(config_dir=config_dir)
        .configure_services(register)
        .configure_pipeline(lambda pipeline: pipeline.map(Route("/greet/{name}", greet)))
        .build()
    )
