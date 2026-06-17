"""Fluent builder for the web host — the bare HTTP substrate, no Web API framework.

Boots config → observability → services → container → Starlette app, wrapping the
transport-agnostic `run_host_lifecycle` in a Starlette lifespan. Extensible only through
`configure_services` (DI) and `configure_pipeline` (routes + ordered middleware); a Web
API framework like FastAPI is layered on top by an integration, never required here.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Sequence
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Self

from opentelemetry.instrumentation.asgi import OpenTelemetryMiddleware
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.routing import BaseRoute

if TYPE_CHECKING:
    from dishka import Provider

from pepelats.configuration import load_configuration
from pepelats.dependency_injection import ServiceCollection, ServiceProvider
from pepelats.dependency_injection.container_factory import build_container
from pepelats.hosting.background_service import BackgroundService
from pepelats.hosting.host_bootstrap import load_host_bootstrap
from pepelats.hosting.host_lifecycle import run_host_lifecycle
from pepelats.hosting.http_di import RequestScopeMiddleware, setup_http_container
from pepelats.hosting.middleware import ExceptionLoggingMiddleware
from pepelats.hosting.pipeline import (
    HostPipeline,
    MiddlewareOrder,
    PipelineConfigurator,
    build_middleware,
    build_routes,
)
from pepelats.hosting.service_configurator import ServiceConfigurator
from pepelats.hosting.web_host import WebHost
from pepelats.observability import (
    configure_observability,
    shutdown_observability,
)

HostLifespan = Callable[[Starlette], AbstractAsyncContextManager[None]]


class WebHostBuilder:
    def __init__(self, *, config_dir: Path) -> None:
        bootstrap = load_host_bootstrap(load_configuration(config_dir))
        self._configuration = bootstrap.configuration
        self._service_config = bootstrap.service_config
        self._environment = bootstrap.environment
        self._host_config = bootstrap.host_config
        self._observability = bootstrap.observability
        self._service_configurators: list[ServiceConfigurator] = []
        self._pipeline_configurators: list[PipelineConfigurator] = []
        self._lifespan: HostLifespan | None = None

    @classmethod
    def create(cls, *, config_dir: Path) -> Self:
        return cls(config_dir=config_dir)

    def configure_services(self, configure: ServiceConfigurator) -> Self:
        self._service_configurators.append(configure)
        return self

    def configure_pipeline(self, configure: PipelineConfigurator) -> Self:
        self._pipeline_configurators.append(configure)
        return self

    def configure_lifespan(self, lifespan: HostLifespan) -> Self:
        self._lifespan = lifespan
        return self

    def build(self) -> WebHost:
        # Observability is configured here (not in the lifespan) so build-time logs
        # and spans are structured and the tracer provider is set before the
        # instrumentation middleware is built. Runtime teardown is owned by the host
        # lifespan (run_host_lifecycle, invoked when the host is served). If build
        # itself fails past this point, undo it so a failed build leaves no global
        # providers running.
        configure_observability(self._observability)
        try:
            collection = ServiceCollection(self._configuration)
            for configure in self._service_configurators:
                configure(collection, self._configuration)

            container = build_container(
                collection,
                service_config=self._service_config,
                environment=self._environment,
                extra_providers=self._extra_providers(),
            )

            pipeline = self._build_pipeline()
            app = self._create_application(
                routes=build_routes(pipeline),
                middleware=build_middleware(pipeline),
                lifespan=self._build_lifespan(
                    container, collection.hosted_service_types
                ),
            )
            setup_http_container(app, container)

            server = self._host_config.server
            return WebHost(
                app,
                bind=server.bind,
                port=server.port,
                shutdown_timeout_seconds=self._host_config.shutdown_timeout_seconds,
            )
        except Exception:
            shutdown_observability()
            raise

    def _extra_providers(self) -> Sequence[Provider]:
        """DI providers to add beyond the registered services. Integrations override
        this to inject engine-specific providers (e.g. request-context)."""
        return ()

    def _create_application(
        self,
        *,
        routes: list[BaseRoute],
        middleware: list[Middleware],
        lifespan: HostLifespan,
    ) -> Starlette:
        """Build the ASGI application. Integrations override to swap in their own app
        type (e.g. FastAPI) while reusing the assembled pipeline and lifecycle."""
        return Starlette(routes=routes, middleware=middleware, lifespan=lifespan)

    def _build_pipeline(self) -> HostPipeline:
        pipeline = HostPipeline()
        # Built-ins claim fixed orders; app/integration middleware slots around them.
        pipeline.use(OpenTelemetryMiddleware, order=MiddlewareOrder.INSTRUMENTATION)
        pipeline.use(ExceptionLoggingMiddleware, order=MiddlewareOrder.EXCEPTION_LOGGING)
        pipeline.use(RequestScopeMiddleware, order=MiddlewareOrder.REQUEST_SCOPE)
        for configure in self._pipeline_configurators:
            configure(pipeline)
        return pipeline

    def _build_lifespan(
        self,
        container: ServiceProvider,
        hosted_service_types: list[type[BackgroundService]],
    ) -> HostLifespan:
        shutdown_timeout = self._host_config.shutdown_timeout_seconds
        app_lifespan = self._lifespan

        @asynccontextmanager
        async def lifespan(app: Starlette) -> AsyncIterator[None]:
            async with run_host_lifecycle(
                container=container,
                hosted_service_types=hosted_service_types,
                shutdown_timeout_seconds=shutdown_timeout,
            ):
                # Optional app startup/shutdown hook for one-off setup; long loops use
                # BackgroundService.
                if app_lifespan is not None:
                    async with app_lifespan(app):
                        yield
                else:
                    yield

        return lifespan
