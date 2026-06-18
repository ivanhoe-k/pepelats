<p align="center">
  <img src="docs/img/logo.png" alt="Pepelats" width="480">
</p>
<p align="center">
  <em>Small Opinionated framework for async web services in Python — compose on a fluent builder with DI, configuration, observability, and lifecycle built in.</em>
</p>
<p align="center">
  <img src="https://img.shields.io/badge/python-3.13+-3776AB?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/version-0.1.0a3-orange" alt="Version">
  <img src="https://img.shields.io/badge/status-experimental-yellow" alt="Status">
  <img src="https://img.shields.io/badge/license-Apache--2.0-blue" alt="License">
</p>

---

Apps compose on `WebHostBuilder` or `FastAPIHostBuilder`: register services, mount routes or APIs, run background workers. Starlette is the HTTP layer; FastAPI is optional.

## Features

- Compose and run an async web service from a single builder
- Inject services and configuration into handlers and constructors
- Load typed settings from TOML or JSON with environment overlays
- Structured logging, tracing, and metrics
- Run background work alongside the HTTP server
- Optional FastAPI for REST APIs and OpenAPI (`pepelats[fastapi]`)

## Installation

```bash
uv add pepelats
uv add "pepelats[fastapi]"
```

## Configuration

Pass a `config_dir` to the builder. Pepelats loads, in order:

1. `appsettings.toml` or `appsettings.json` (required)
2. `appsettings.{Environment}.*` when present
3. `.env`, then process environment variables (highest priority)

The environment name comes from `ENVIRONMENT`, the `environment` key in the base file, or defaults to `Local`. That name selects the overlay file (e.g. `appsettings.Staging.toml`).

`config/appsettings.toml`:

```toml
environment = "Local"

[service]
service_name = "my-service"
service_version = "1.0.0"

[logging]
log_level = "INFO"
sinks = ["console"]

[logging.console]
json_logs = false

[host]
bind = "127.0.0.1"
port = 8000

[observability]
enabled = false
otlp_endpoint = ""

[greeting]
punctuation = "!"
shout = false
```

Overlay example (`config/appsettings.Staging.toml`):

```toml
[host]
port = 8080
```

Environment variables override file values. Nested keys use `__`:

```bash
ENVIRONMENT=Production
HOST__PORT=9001
LOGGING__LOG_LEVEL=DEBUG
```

Host bootstrap requires `[service]`, `[logging]`, `[host]`, and `[observability]`. Set `observability.enabled = true` only with a non-empty `otlp_endpoint`.

App settings use Pydantic models registered with `add_configuration`. By default, `{Name}Config` maps to a `[name]` section in snake_case (`LoggingConfig` → `logging`, `MessageBusConfig` → `message_bus`). This works when each word is PascalCase with a single leading capital. Otherwise, pass `section=` to set the section name yourself.

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

Runnable apps live under [`examples/`](examples/). Each folder has a short README and a `main.py` you can run from the repo root:

```bash
uv run python examples/starlette-basic/main.py
uv run python examples/fastapi-basic/main.py
uv run python examples/background-worker/main.py
uv run python examples/observability/main.py
```

| Example | What it shows |
|---------|----------------|
| `starlette-basic/` | Generic host, manual DI with `request_services` |
| `fastapi-basic/` | FastAPI host, `Inject[T]` on routes |
| `background-worker/` | `BackgroundService` with a status route |
| `observability/` | Structured logging and spans on a request |

Shared wiring for the greeting examples is in `examples/shared/`. Smoke tests: `tests/example_smoke/`.

See [examples/README.md](examples/README.md) for per-example notes.

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
