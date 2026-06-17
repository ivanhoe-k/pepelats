"""The mount hook for the HTTP API surface.

The app registers routers and middleware on the FastAPI app here. Core ships no opinion
about which features exist; REST is just the app calling ``include_router``, and external
packages (GraphQL, gRPC) use the same hook.
"""

from collections.abc import Callable

from fastapi import FastAPI

ApiConfigurator = Callable[[FastAPI], None]


def apply_api_configurators(
    app: FastAPI,
    configurators: list[ApiConfigurator],
) -> None:
    for configure in configurators:
        configure(app)
