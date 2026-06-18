# Starlette basic

Generic `WebHostBuilder` with a single route. Dependencies are resolved manually from the request scope:

```python
services = request_services(request)
greeter = await services.get(Greeter)
```

Configuration lives in [`appsettings.toml`](appsettings.toml) next to this file.

Run:

```bash
uv run python examples/starlette-basic/main.py
```

Then `GET http://127.0.0.1:8099/greet/ada` → `{"message":"HELLO, ADA!","count":1}`.
