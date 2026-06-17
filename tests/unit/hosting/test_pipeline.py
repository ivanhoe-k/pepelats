"""Unit tests for HostPipeline ordering and route registration."""

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.types import ASGIApp, Receive, Scope, Send

from pepelats.hosting.pipeline import (
    HostPipeline,
    MiddlewareOrder,
    build_middleware,
    build_routes,
)


class _Outer:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        await self.app(scope, receive, send)


class _Inner(_Outer):
    pass


class _AlsoInner(_Outer):
    pass


def test_build_middleware_sorts_by_ascending_order() -> None:
    pipeline = HostPipeline()
    pipeline.use(_Inner, order=300)
    pipeline.use(_Outer, order=100)

    classes: list[object] = [
        middleware.cls for middleware in build_middleware(pipeline)
    ]

    assert classes == [_Outer, _Inner]


def test_build_middleware_keeps_insertion_order_for_equal_orders() -> None:
    pipeline = HostPipeline()
    pipeline.use(_Inner, order=100)
    pipeline.use(_AlsoInner, order=100)

    classes: list[object] = [
        middleware.cls for middleware in build_middleware(pipeline)
    ]

    assert classes == [_Inner, _AlsoInner]


def test_builtin_orders_sort_outer_to_inner() -> None:
    pipeline = HostPipeline()
    pipeline.use(_Inner, order=MiddlewareOrder.REQUEST_SCOPE)
    pipeline.use(_AlsoInner, order=MiddlewareOrder.INSTRUMENTATION)
    pipeline.use(_Outer, order=MiddlewareOrder.EXCEPTION_LOGGING)

    classes: list[object] = [
        middleware.cls for middleware in build_middleware(pipeline)
    ]

    assert classes == [_AlsoInner, _Outer, _Inner]


def test_use_forwards_options_to_middleware() -> None:
    pipeline = HostPipeline()
    pipeline.use(_Outer, order=1, header_name="x-trace")

    middleware = build_middleware(pipeline)[0]

    assert middleware.kwargs == {"header_name": "x-trace"}


def test_map_accumulates_routes_in_order() -> None:
    async def endpoint(_: Request) -> JSONResponse:
        return JSONResponse({})

    pipeline = HostPipeline()
    first = Route("/a", endpoint)
    second = Route("/b", endpoint)

    pipeline.map(first)
    pipeline.map(second)

    assert build_routes(pipeline) == [first, second]
