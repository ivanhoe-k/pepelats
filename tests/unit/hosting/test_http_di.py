"""Tests for request-scoped DI over HTTP (RequestScopeMiddleware + request_services).

Driven through a minimal in-test Starlette app via TestClient — no full host. The
TestClient context manager runs the ASGI lifespan, but these tests exercise only the
request path.
"""

from collections.abc import Callable

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient
from starlette.types import Receive, Scope, Send

from pepelats.dependency_injection.async_disposable import AsyncDisposable
from pepelats.dependency_injection.service_collection import ServiceCollection
from pepelats.dependency_injection.service_provider import ServiceProvider
from pepelats.hosting.http_di import (
    RequestScopeMiddleware,
    request_services,
    setup_http_container,
)

BuildProvider = Callable[[Callable[[ServiceCollection], object]], ServiceProvider]


class ScopedToken:
    pass


class DisposeCounter(AsyncDisposable):
    """Scoped disposable that counts disposals across requests."""

    count = 0

    def __init__(self) -> None:
        pass

    async def dispose(self) -> None:
        type(self).count += 1


def _client(provider: ServiceProvider, endpoint: Callable[..., object]) -> TestClient:
    app = Starlette(
        routes=[Route("/", endpoint)],
        middleware=[Middleware(RequestScopeMiddleware)],
    )
    setup_http_container(app, provider)
    return TestClient(app)


def test_request_services_resolves_a_per_request_scope(
    build_provider: BuildProvider,
) -> None:
    provider = build_provider(lambda services: services.add_scoped(ScopedToken))

    async def endpoint(request: Request) -> JSONResponse:
        token = await request_services(request).get(ScopedToken)
        return JSONResponse({"token_id": id(token)})

    with _client(provider, endpoint) as client:
        first = client.get("/").json()["token_id"]
        second = client.get("/").json()["token_id"]

    assert first != second  # a fresh scope per request


def test_request_scope_is_closed_after_response(
    build_provider: BuildProvider,
) -> None:
    DisposeCounter.count = 0
    provider = build_provider(lambda services: services.add_scoped(DisposeCounter))

    async def endpoint(request: Request) -> JSONResponse:
        await request_services(request).get(DisposeCounter)
        return JSONResponse({})

    with _client(provider, endpoint) as client:
        client.get("/")

    assert DisposeCounter.count == 1


async def test_non_http_scope_passes_through_without_a_scope() -> None:
    seen: list[str] = []

    async def downstream(scope: Scope, receive: Receive, send: Send) -> None:
        seen.append(scope["type"])

    async def receive() -> dict[str, object]:
        return {"type": "lifespan.startup"}

    async def send(_: object) -> None:
        return None

    middleware = RequestScopeMiddleware(downstream)

    await middleware({"type": "lifespan"}, receive, send)

    assert seen == ["lifespan"]
