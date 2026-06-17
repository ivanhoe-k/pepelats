"""Runnable FastAPI example exercising every DI shape a route can ask for.

Kept as a living reference (and regression anchor) for how `Inject[T]` resolves
different registrations through `pepelats`. One route receives:

1. a service behind an interface       — `Inject[Greeter]`
2. a concrete service, registered as-is — `Inject[RequestCounter]`
3. a typed configuration section        — `Inject[GreetingConfig]`
4. a service with multiple generic args — `Inject[Repository[User, int]]`

plus OTel logging/tracing via `get_logger` and `span`. It boots through
`FastAPIHostBuilder`, exactly like a real app.
"""

from abc import ABC, abstractmethod
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

from pepelats.configuration import Configuration
from pepelats.dependency_injection import Inject, ServiceCollection
from pepelats.hosting.web_host import WebHost
from pepelats.integrations.fastapi import FastAPIHostBuilder, InjectRoute
from pepelats.observability import get_logger, span

logger = get_logger(__name__)


# 1. Service behind an interface — register the contract, resolve the implementation.
class Greeter(ABC):
    @abstractmethod
    def greet(self, name: str) -> str: ...


class FriendlyGreeter(Greeter):
    def greet(self, name: str) -> str:
        return f"Hello, {name}"


# 2. Concrete service, registered as itself. Singleton, so state survives requests.
class RequestCounter:
    def __init__(self) -> None:
        self._count = 0

    def increment(self) -> int:
        self._count += 1
        return self._count


# 3. Typed configuration — bound to the [default.greeting] TOML section by name.
class GreetingConfig(BaseModel):
    punctuation: str
    shout: bool


# 4. Service with multiple generic args. The open generic is registered once; the
#    closed alias `Repository[User, int]` is what the route asks for.
class User(BaseModel):
    id: int
    name: str


class Repository[TEntity, TKey]:
    def __init__(self) -> None:
        self._items: dict[object, object] = {}

    def count(self) -> int:
        return len(self._items)


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


def register(services: ServiceCollection, configuration: Configuration) -> None:
    # Registering an abstract interface as a DI key is the intent; mypy's
    # type-abstract guard targets accidental instantiation, not this.
    services.add_scoped(Greeter, FriendlyGreeter)  # type: ignore[type-abstract]
    services.add_singleton(RequestCounter)
    services.add_configuration(GreetingConfig)
    services.add_scoped(Repository)


_APPSETTINGS = """\
[default]
environment = "local"

[default.service]
service_name = "di-showcase"
service_version = "1.0.0"

[default.logging]
log_level = "INFO"
sinks = ["console"]

[default.logging.console]
json_logs = false

[default.host]
bind = "127.0.0.1"
port = 8099

[default.observability]
otlp_endpoint = ""

[default.greeting]
punctuation = "!"
shout = true
"""


def write_config(config_dir: Path) -> Path:
    (config_dir / "appsettings.toml").write_text(_APPSETTINGS, encoding="utf-8")
    return config_dir


def build_host(config_dir: Path) -> WebHost:
    return (
        FastAPIHostBuilder.create(config_dir=config_dir)
        .configure_services(register)
        .configure_api(lambda app: app.include_router(router))
        .build()
    )
