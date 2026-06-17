<p align="center">
  <img src="docs/img/logo.png" alt="Pepelats" width="480">
</p>
<p align="center">
  <em>Opinionated framework for async web services in Python — compose on a fluent builder with DI, configuration, observability, and lifecycle built in.</em>
</p>
<p align="center">
  <img src="https://img.shields.io/badge/python-3.13+-3776AB?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/version-0.1.0a1-orange" alt="Version">
  <img src="https://img.shields.io/badge/status-experimental-yellow" alt="Status">
  <img src="https://img.shields.io/badge/license-Apache--2.0-blue" alt="License">
</p>

---

Apps compose on `WebHostBuilder` or `FastAPIHostBuilder`: register services, mount routes or APIs, run background workers. Starlette is the HTTP layer; FastAPI is optional.

## Features

- Compose and run an async web service from a single builder
- Inject services and configuration into handlers and constructors
- Load typed settings from TOML and environment variables
- Structured logging, tracing, and metrics
- Run background work alongside the HTTP server
- Optional FastAPI for REST APIs and OpenAPI (`pepelats[fastapi]`)

## Installation

```bash
uv add pepelats
uv add "pepelats[fastapi]"
```

## Configuration

Pass a `config_dir` to the builder. Pepelats loads `appsettings.toml` from that directory (and merges `appsettings.local.toml` when present). Set the active environment with the `ENVIRONMENT` variable (defaults to `default`).

`config/appsettings.toml`:

```toml
[default]
environment = "local"

[default.service]
service_name = "my-service"
service_version = "1.0.0"

[default.logging]
log_level = "INFO"
sinks = ["console"]

[default.logging.console]
json_logs = false

[default.host]
bind = "127.0.0.1"
port = 8000

[default.observability]
enabled = false
otlp_endpoint = ""

[default.greeting]
punctuation = "!"
shout = false
```

`service`, `logging`, `host`, and `observability` are required for host bootstrap. `enabled` is the OTLP export switch: `false` runs local-only (console/file logs, no collector); `true` requires a non-empty `otlp_endpoint` (an empty one is a config error, not a silent opt-out). `export_timeout_seconds` (default `3`) caps every OTLP export, including the final flush on shutdown — so an unreachable collector can't stall teardown. The flush runs to completion before the process exits, so shutdown leaves no straggling export logs.

App-specific sections bind to Pydantic models. The section name defaults to the model name in snake_case (`GreetingConfig` → `greeting`). Register with `add_configuration`; services receive the config through constructor injection:

```python
from pydantic import BaseModel

from pepelats.configuration import Configuration
from pepelats.dependency_injection import ServiceCollection


class GreetingConfig(BaseModel):
    punctuation: str
    shout: bool


class HealthService:
    def __init__(self, config: GreetingConfig) -> None:
        self._config = config

    def status(self) -> str:
        message = "ok"
        if self._config.shout:
            message = message.upper()
        return message + self._config.punctuation


def register(services: ServiceCollection, configuration: Configuration) -> None:
    services.add_configuration(GreetingConfig)
    services.add_singleton(HealthService)
```

## Examples

Runnable full versions: `tests/examples/di_showcase_generic.py` (Starlette) and `tests/examples/di_showcase.py` (FastAPI).

### Generic host

```python
from pathlib import Path

from pydantic import BaseModel
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from pepelats.configuration import Configuration
from pepelats.dependency_injection import ServiceCollection
from pepelats.hosting import HostPipeline, WebHostBuilder, request_services
from pepelats.hosting.web_host import WebHost


class GreetingConfig(BaseModel):
    punctuation: str
    shout: bool


class HealthService:
    def __init__(self, config: GreetingConfig) -> None:
        self._config = config

    def status(self) -> str:
        message = "ok"
        if self._config.shout:
            message = message.upper()
        return message + self._config.punctuation


async def health(request: Request) -> JSONResponse:
    services = request_services(request)
    service = await services.get(HealthService)
    return JSONResponse({"status": service.status()})


def register(services: ServiceCollection, configuration: Configuration) -> None:
    services.add_configuration(GreetingConfig)
    services.add_singleton(HealthService)


def map_routes(pipeline: HostPipeline) -> None:
    pipeline.map(Route("/health", health))


def build_host(config_dir: Path) -> WebHost:
    return (
        WebHostBuilder.create(config_dir=config_dir)
        .configure_services(register)
        .configure_pipeline(map_routes)
        .build()
    )


if __name__ == "__main__":
    build_host(Path("config")).run()
```

### FastAPI

```python
from pathlib import Path

from fastapi import APIRouter, FastAPI
from pydantic import BaseModel

from pepelats.configuration import Configuration
from pepelats.dependency_injection import Inject, ServiceCollection
from pepelats.hosting.web_host import WebHost
from pepelats.integrations.fastapi import FastAPIHostBuilder, InjectRoute


class GreetingConfig(BaseModel):
    punctuation: str
    shout: bool


class HealthService:
    def __init__(self, config: GreetingConfig) -> None:
        self._config = config

    def status(self) -> str:
        message = "ok"
        if self._config.shout:
            message = message.upper()
        return message + self._config.punctuation


router = APIRouter(route_class=InjectRoute)


@router.get("/health")
async def health(service: Inject[HealthService]) -> dict[str, str]:
    return {"status": service.status()}


def register(services: ServiceCollection, configuration: Configuration) -> None:
    services.add_configuration(GreetingConfig)
    services.add_singleton(HealthService)


def configure_api(app: FastAPI) -> None:
    app.include_router(router)


def build_host(config_dir: Path) -> WebHost:
    return (
        FastAPIHostBuilder.create(config_dir=config_dir)
        .configure_services(register)
        .configure_api(configure_api)
        .build()
    )


if __name__ == "__main__":
    build_host(Path("config")).run()
```

## Dependencies

Pepelats uses:

* [Starlette](https://www.starlette.io/) and [Uvicorn](https://www.uvicorn.org/) — ASGI application and server
* [Dishka](https://github.com/reagento/dishka) — dependency injection
* [Dynaconf](https://www.dynaconf.com/) and [Pydantic](https://docs.pydantic.dev/) — configuration
* [structlog](https://www.structlog.org/) — structured logging
* [OpenTelemetry](https://opentelemetry.io/) — tracing and metrics

Optional:

* [FastAPI](https://fastapi.tiangolo.com/) — API layer (`pepelats[fastapi]`)

## License

Apache-2.0 — see [LICENSE](LICENSE).
