# Observability

Minimal host with one route, focused on Pepelats logging and tracing — no DI or background workers.

## What it shows

- **Host bootstrap** — `[service]`, `[logging]`, and `[observability]` in config drive structured logging and OpenTelemetry setup at startup.
- **HTTP tracing** — the host adds ASGI instrumentation; every request gets a server span automatically.
- **App-level APIs** — the handler adds its own span and structured log line:

```python
with span("hello.handle"):
    logger.info("hello.request", path=str(request.url.path))
```

Shared wiring lives in [`../shared/observability_host.py`](../shared/observability_host.py).

## Configuration

Settings are in [`appsettings.toml`](appsettings.toml) next to this file. By default OTLP export is off — logs go to the console only.

To send traces, logs, and metrics to a collector, enable export:

```toml
[observability]
enabled = true
otlp_endpoint = "http://127.0.0.1:4318"
```

Or override at runtime:

```bash
export OBSERVABILITY__ENABLED=true
export OBSERVABILITY__OTLP_ENDPOINT=http://127.0.0.1:4318
```

## Run

From the repo root:

```bash
uv run python examples/observability/main.py
```

Then:

```http
GET http://127.0.0.1:8099/hello
```

Response: `{"status":"ok"}`.

With default config you should see a structured `hello.request` log line in the console. With OTLP enabled, spans and logs also export to your collector.
