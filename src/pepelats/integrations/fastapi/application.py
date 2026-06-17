"""FastAPI application factory.

Builds the FastAPI app from the host-assembled pipeline (routes + middleware) and
lifecycle, then lets the app mount its API surface via the configurators. FastAPI is a
Starlette subclass, so it reuses the core host's middleware and lifespan unchanged.
"""

from collections.abc import Sequence

from fastapi import FastAPI
from starlette.middleware import Middleware
from starlette.routing import BaseRoute

from pepelats.configuration import ServiceConfig
from pepelats.hosting import HostLifespan
from pepelats.integrations.fastapi.api_configurator import (
    ApiConfigurator,
    apply_api_configurators,
)


def create_fastapi_application(
    *,
    service_config: ServiceConfig,
    routes: Sequence[BaseRoute],
    middleware: Sequence[Middleware],
    lifespan: HostLifespan,
    api_configurators: list[ApiConfigurator],
) -> FastAPI:
    app = FastAPI(
        title=service_config.service_name,
        version=service_config.service_version,
        routes=list(routes) or None,
        middleware=list(middleware),
        lifespan=lifespan,
    )
    apply_api_configurators(app, api_configurators)
    return app
