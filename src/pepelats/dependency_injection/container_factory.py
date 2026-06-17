"""Turns a ServiceCollection into a runnable container (the ServiceProvider adapter).

Host-loaded configs (service identity, environment) enter the container via Dishka
`from_context` rather than re-registration, so bootstrap stays the single load path.
Integrations extend the container with their own providers via `extra_providers`
(e.g. the FastAPI integration adds request-context providers) — core stays closed.
"""

from collections.abc import Sequence

from dishka import Provider, Scope, make_async_container

from pepelats.configuration import Environment, ServiceConfig
from pepelats.dependency_injection.service_collection import (
    ServiceCollection,
    registration_provider,
)
from pepelats.dependency_injection.service_provider import (
    DishkaServiceProvider,
    ServiceProvider,
)


def build_container(
    collection: ServiceCollection,
    *,
    service_config: ServiceConfig,
    environment: Environment,
    extra_providers: Sequence[Provider] = (),
) -> ServiceProvider:
    host_provider = Provider()
    host_provider.from_context(provides=ServiceConfig, scope=Scope.APP)
    host_provider.from_context(provides=Environment, scope=Scope.APP)

    container = make_async_container(
        registration_provider(collection),
        host_provider,
        *extra_providers,
        context={
            ServiceConfig: service_config,
            Environment: environment,
        },
    )
    return DishkaServiceProvider(container)
