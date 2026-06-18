# Background worker

A `BackgroundService` runs for the lifetime of the host. A `/status` route reads worker state through DI.

Configuration lives in [`appsettings.toml`](appsettings.toml) next to this file.

Run:

```bash
uv run python examples/background-worker/main.py
```

Poll `GET http://127.0.0.1:8099/status` — `ticks` increases about once per second while the host is up.
