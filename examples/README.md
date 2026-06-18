# Pepelats examples

Runnable reference apps. Run from the repo root:

```bash
uv run python examples/starlette-basic/main.py
uv run python examples/fastapi-basic/main.py
uv run python examples/background-worker/main.py
uv run python examples/observability/main.py
```

| Example | Shows |
|---------|--------|
| [starlette-basic](starlette-basic/) | Generic `WebHostBuilder`, manual DI via `request_services` |
| [fastapi-basic](fastapi-basic/) | `FastAPIHostBuilder`, `Inject[T]` on routes |
| [background-worker](background-worker/) | `BackgroundService` lifecycle with the HTTP host |
| [observability](observability/) | Structured logging and tracing spans on a request |

Each example folder has an `appsettings.toml` beside `main.py`. Shared greeting services live in [shared/greeting.py](shared/greeting.py); the HTTP examples reuse them.

Smoke tests: `tests/example_smoke/`.
