"""FastAPI host builder — the Web API layer over the web host.

Composes `WebHostBuilder` by overriding two seams: the DI providers (adds the
request-context `RequestProvider`) and the application factory (builds FastAPI and mounts
the API surface). Everything else — config, observability, container, pipeline,
lifecycle — is inherited unchanged.
"""

from collections.abc import Sequence
from pathlib import Path
from typing import Self

from dishka import Provider
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.routing import BaseRoute

from pepelats.hosting import HostLifespan, WebHostBuilder
from pepelats.integrations.fastapi.api_configurator import ApiConfigurator
from pepelats.integrations.fastapi.application import create_fastapi_application
from pepelats.integrations.fastapi.route_injection import RequestProvider


class FastAPIHostBuilder(WebHostBuilder):
    def __init__(self, *, config_dir: Path) -> None:
        super().__init__(config_dir=config_dir)
        self._api_configurators: list[ApiConfigurator] = []

    def configure_api(self, configure: ApiConfigurator) -> Self:
        self._api_configurators.append(configure)
        return self

    def _extra_providers(self) -> Sequence[Provider]:
        return (RequestProvider(),)

    def _create_application(
        self,
        *,
        routes: list[BaseRoute],
        middleware: list[Middleware],
        lifespan: HostLifespan,
    ) -> Starlette:
        return create_fastapi_application(
            service_config=self._service_config,
            routes=routes,
            middleware=middleware,
            lifespan=lifespan,
            api_configurators=self._api_configurators,
        )
