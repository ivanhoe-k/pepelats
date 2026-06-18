"""FastAPI greeting host — importable from tests and the fastapi-basic example."""

from pathlib import Path

from fastapi import APIRouter

from examples.shared.greeting import (
    Greeter,
    GreetingConfig,
    Repository,
    RequestCounter,
    User,
    register,
)
from pepelats.dependency_injection import Inject
from pepelats.hosting.web_host import WebHost
from pepelats.integrations.fastapi import FastAPIHostBuilder, InjectRoute
from pepelats.observability import get_logger, span

logger = get_logger(__name__)

router = APIRouter(route_class=InjectRoute)


@router.get("/greet/{name}")
async def greet(
    name: str,
    greeter: Inject[Greeter],
    counter: Inject[RequestCounter],
    config: Inject[GreetingConfig],
    users: Inject[Repository[User, int]],
) -> dict[str, str | int]:
    message = greeter.greet(name)
    if config.shout:
        message = message.upper()
    message += config.punctuation
    count = counter.increment()

    with span("greet.handle"):
        logger.info("greeted", name=name, count=count, known_users=users.count())

    return {"message": message, "count": count}


def build_host(config_dir: Path) -> WebHost:
    return (
        FastAPIHostBuilder.create(config_dir=config_dir)
        .configure_services(register)
        .configure_api(lambda app: app.include_router(router))
        .build()
    )
