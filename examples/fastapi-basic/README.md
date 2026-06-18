# FastAPI basic

`FastAPIHostBuilder` with `InjectRoute` so route handlers declare dependencies as parameters:

```python
async def greet(name: str, greeter: Inject[Greeter], ...) -> dict[str, str | int]:
    ...
```

Configuration lives in [`appsettings.toml`](appsettings.toml) next to this file.

Run:

```bash
uv run python examples/fastapi-basic/main.py
```

Same `/greet/{name}` response as the Starlette example; only the transport and DI surface differ.
