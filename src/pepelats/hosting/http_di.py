"""Request-scoped DI for HTTP transports — one DI scope per request, reachable from handlers.

`RequestScopeMiddleware` opens a REQUEST scope per connection and publishes its
`ServiceProvider` on the connection state. `request_services` reads it back, so routes,
GraphQL resolvers, and WebSocket handlers depend on the accessor — never on the
container or its state key. `setup_http_container` hands the root provider to the app so
the middleware can derive per-request scopes from it.

The connection (`Request`/`WebSocket`) is seeded into the scope context, so providers
that consume it (e.g. the FastAPI integration's `RequestProvider`) resolve it like any
dependency.
"""

from typing import Any

from starlette.applications import Starlette
from starlette.requests import HTTPConnection, Request
from starlette.types import ASGIApp, Receive, Scope, Send
from starlette.websockets import WebSocket

from pepelats.dependency_injection import ServiceProvider

# Namespaced to avoid colliding with app-set keys on connection/app state.
_PROVIDER_STATE_KEY = "pepelats.request_service_provider"


def setup_http_container(app: Starlette, provider: ServiceProvider) -> None:
    """Publish the root provider on the app so request middleware can scope from it."""
    setattr(app.state, _PROVIDER_STATE_KEY, provider)


class RequestScopeMiddleware:
    """Opens a REQUEST scope per HTTP/WebSocket connection and publishes its provider."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        context = _scope_context(scope, receive, send)
        if context is None:
            await self.app(scope, receive, send)
            return

        root: ServiceProvider = getattr(scope["app"].state, _PROVIDER_STATE_KEY)
        async with root.enter_scope(context) as request_provider:
            scope.setdefault("state", {})[_PROVIDER_STATE_KEY] = request_provider
            await self.app(scope, receive, send)


def _scope_context(scope: Scope, receive: Receive, send: Send) -> dict[Any, Any] | None:
    """Seed the per-request scope with the connection; None for non-HTTP scopes.

    This builds a connection object so providers (e.g. the FastAPI integration's
    `RequestProvider`) can resolve `Request`/`WebSocket` by type. It shares the same
    ASGI `scope`/`receive` as the connection the route handler sees, so request state
    is shared — but the body stream can be consumed only once: read it from one
    `Request`, not from both an injected and a parameter `Request`.
    """
    if scope["type"] == "http":
        return {Request: Request(scope, receive, send)}
    if scope["type"] == "websocket":
        return {WebSocket: WebSocket(scope, receive, send)}
    return None


def request_services(connection: HTTPConnection) -> ServiceProvider:
    """Resolve the `ServiceProvider` scoped to the current request/connection."""
    provider: ServiceProvider = getattr(connection.state, _PROVIDER_STATE_KEY)
    return provider
