"""The host's HTTP pipeline — ordered middleware plus routes.

Apps and integrations extend the host through `HostPipeline`: `use` adds ASGI
middleware at a chosen order, `map` adds a route. Built-ins claim fixed orders in
`MiddlewareOrder`; everything else is open, so new middleware (auth, CORS, GraphQL)
slots in without core edits. Lower order runs further out (closer to the network).
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Self

from starlette.middleware import Middleware
from starlette.routing import BaseRoute
from starlette.types import ASGIApp

# An ASGI middleware factory: called with the next app (plus options) and returns the
# wrapping app. Middleware classes satisfy this via their constructor.
ASGIMiddlewareFactory = Callable[..., ASGIApp]


class MiddlewareOrder(IntEnum):
    """Fixed orders for built-in middleware. Apps pick any int around these."""

    INSTRUMENTATION = 100
    EXCEPTION_LOGGING = 200
    REQUEST_SCOPE = 300


@dataclass(frozen=True, slots=True)
class _MiddlewareRegistration:
    order: int
    middleware: ASGIMiddlewareFactory
    options: dict[str, Any]


@dataclass(slots=True)
class HostPipeline:
    _middleware: list[_MiddlewareRegistration] = field(default_factory=list)
    _routes: list[BaseRoute] = field(default_factory=list)

    def use(
        self, middleware: ASGIMiddlewareFactory, *, order: int, **options: Any
    ) -> Self:
        """Add ASGI middleware at the given order (lower runs further out)."""
        self._middleware.append(_MiddlewareRegistration(order, middleware, options))
        return self

    def map(self, route: BaseRoute) -> Self:
        """Add a route to the host."""
        self._routes.append(route)
        return self


PipelineConfigurator = Callable[[HostPipeline], None]


def build_middleware(pipeline: HostPipeline) -> list[Middleware]:
    """Package-internal: ordered Starlette middleware from the pipeline."""
    ordered = sorted(pipeline._middleware, key=lambda entry: entry.order)
    return [Middleware(entry.middleware, **entry.options) for entry in ordered]


def build_routes(pipeline: HostPipeline) -> list[BaseRoute]:
    """Package-internal: routes registered on the pipeline."""
    return list(pipeline._routes)
