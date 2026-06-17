"""FastAPI route injection — resolves `Inject[T]` params from the request provider.

`InjectRoute` is our `APIRoute`: it rewrites the endpoint so parameters marked with
`Inject[T]` leave the OpenAPI/validation surface and are resolved from the per-request
`ServiceProvider` instead. `RequestProvider` makes the HTTP connection (`Request`/
`WebSocket`) resolvable by type within the request scope.

Resolution goes through the `ServiceProvider` abstraction (`get`), so this integration
depends on the DI contract, not on the concrete engine. The `Inject` marker is our own
(see `dependency_injection.inject`), so the app-facing injection surface is engine-neutral
too. `RequestProvider` is the one Dishka-specific piece — it extends the container to make
the HTTP connection injectable, which is inherently engine-coupled.
"""

from collections.abc import Awaitable, Callable
from inspect import Parameter, Signature, signature
from typing import Any, cast, get_type_hints

from dishka import Provider, Scope, from_context
from fastapi import Request, WebSocket
from fastapi.routing import APIRoute
from starlette.requests import HTTPConnection

from pepelats.dependency_injection.inject import injected_type
from pepelats.hosting.http_di import request_services

_REQUEST_PARAM = Parameter(
    "__socia_request", kind=Parameter.KEYWORD_ONLY, annotation=Request
)
_WEBSOCKET_PARAM = Parameter(
    "__socia_websocket", kind=Parameter.KEYWORD_ONLY, annotation=WebSocket
)


class RequestProvider(Provider):
    """Makes the HTTP connection injectable within the request scope."""

    request = from_context(Request, scope=Scope.REQUEST)


class InjectRoute(APIRoute):
    def __init__(self, path: str, endpoint: Callable[..., Any], **kwargs: Any) -> None:
        super().__init__(path, _inject(endpoint), **kwargs)


def _inject[**P, T](func: Callable[P, T]) -> Callable[P, T]:
    hints = get_type_hints(func, include_extras=True)
    func_signature = signature(func)

    injected = _injected_dependencies(func_signature, hints)
    if not injected:
        return func

    # The wrapper needs a connection to reach the request scope. Use the one the
    # handler already declares; otherwise FastAPI supplies hidden ones for us.
    connection_param = _find_connection_param(func)
    additional_params: list[Parameter] = []
    if connection_param is None:
        additional_params = [_REQUEST_PARAM, _WEBSOCKET_PARAM]

    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        connection = _connection_from(connection_param, kwargs)
        provider = request_services(connection)
        for name, dependency_type in injected.items():
            kwargs[name] = await provider.get(dependency_type)
        return await cast(Callable[..., Awaitable[T]], func)(*args, **kwargs)

    _copy_metadata(wrapper, func)
    wrapper.__signature__ = _injected_signature(  # type: ignore[attr-defined]
        func_signature, hints, injected, additional_params
    )
    wrapper.__annotations__ = _injected_annotations(hints, injected, additional_params)
    return cast(Callable[P, T], wrapper)


def _injected_dependencies(
    func_signature: Signature, hints: dict[str, Any]
) -> dict[str, Any]:
    """Map each `Inject[T]` parameter name to its resolved type `T`."""
    dependencies: dict[str, Any] = {}
    for name in func_signature.parameters:
        dependency_type = injected_type(hints.get(name, Any))
        if dependency_type is not None:
            dependencies[name] = dependency_type
    return dependencies


def _connection_from(
    connection_param: str | None, kwargs: dict[str, Any]
) -> HTTPConnection:
    if connection_param is not None:
        return cast(HTTPConnection, kwargs[connection_param])
    # Hidden params: FastAPI populates whichever matches the transport; remove them so
    # they never reach a handler that did not declare them.
    request = kwargs.pop(_REQUEST_PARAM.name, None)
    websocket = kwargs.pop(_WEBSOCKET_PARAM.name, None)
    return cast(HTTPConnection, request or websocket)


def _find_connection_param(func: Callable[..., Any]) -> str | None:
    hints = get_type_hints(func, include_extras=True)
    parameters = signature(func).parameters
    request_param: str | None = None
    websocket_param: str | None = None
    for name, hint in hints.items():
        param = parameters.get(name)
        if param is None or injected_type(hint) is not None:
            continue
        if hint is Request:
            request_param = name
        elif hint is WebSocket:
            websocket_param = name
    return request_param or websocket_param


def _injected_signature(
    func_signature: Signature,
    hints: dict[str, Any],
    injected: dict[str, Any],
    additional_params: list[Parameter],
) -> Signature:
    """Signature without the injected params (+ any hidden connection params).

    This is what FastAPI inspects, so the injected params leave the OpenAPI and
    validation surface while the hidden connection params (typed `Request`/`WebSocket`)
    are recognized and supplied by FastAPI without appearing in the schema.
    """
    params = [
        param.replace(annotation=hints.get(name, param.annotation))
        for name, param in func_signature.parameters.items()
        if name not in injected
    ]
    return Signature(
        _with_additional(params, additional_params),
        return_annotation=func_signature.return_annotation,
    )


def _injected_annotations(
    hints: dict[str, Any],
    injected: dict[str, Any],
    additional_params: list[Parameter],
) -> dict[str, Any]:
    annotations = {name: hint for name, hint in hints.items() if name not in injected}
    for param in additional_params:
        annotations[param.name] = param.annotation
    return annotations


def _with_additional(
    params: list[Parameter], additional: list[Parameter]
) -> list[Parameter]:
    if not additional:
        return params
    # Keyword-only additions must precede a trailing **kwargs to keep the signature
    # well-ordered.
    var_keyword = [p for p in params if p.kind is Parameter.VAR_KEYWORD]
    positional = [p for p in params if p.kind is not Parameter.VAR_KEYWORD]
    return [*positional, *additional, *var_keyword]


def _copy_metadata(wrapper: Callable[..., Any], func: Callable[..., Any]) -> None:
    wrapper.__name__ = func.__name__
    wrapper.__qualname__ = func.__qualname__
    wrapper.__doc__ = func.__doc__
    wrapper.__module__ = func.__module__
