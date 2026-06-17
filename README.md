<p align="center">
  <img src="docs/img/logo.png" alt="Pepelats" width="480">
</p>
<p align="center">
  <em>Async service host for Python — configuration, dependency injection, observability, and HTTP lifecycle.</em>
</p>
<p align="center">
  <img src="https://img.shields.io/badge/python-3.13+-3776AB?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/version-0.1.0-orange" alt="Version">
  <img src="https://img.shields.io/badge/status-experimental-yellow" alt="Status">
  <img src="https://img.shields.io/badge/license-Apache--2.0-blue" alt="License">
</p>

---

Extracted from setups that repeated across projects: load settings, register services, configure logging and tracing, wire middleware and routes, run background workers, shut down in order.

## Features

- Host builder with a fixed startup and shutdown sequence
- Dependency injection with APP and REQUEST scopes
- Configuration from files and environment variables
- Structured logging, tracing, and metrics (OTLP export)
- Hosted background services
- Optional FastAPI integration (`pepelats[fastapi]`)

The core host uses Starlette. FastAPI is optional.

## Installation

```bash
uv add pepelats
uv add "pepelats[fastapi]"
```

## Example

```python
from pathlib import Path

from starlette.routing import Route
from pepelats.hosting import WebHostBuilder

host = (
    WebHostBuilder.create(config_dir=Path("config"))
    .configure_services(lambda services, _: services.add_singleton(MyService))
    .configure_pipeline(lambda pipeline: pipeline.map(Route("/health", health)))
    .build()
)
host.run()
```

More examples: `tests/examples/`.

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
