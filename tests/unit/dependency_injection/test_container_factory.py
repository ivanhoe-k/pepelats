"""Unit tests for build_container host-context wiring."""

from dishka import Provider, Scope
from doubles import FakeSettings

from pepelats.configuration import Environment, ServiceConfig
from pepelats.configuration.configuration import DynaconfConfiguration
from pepelats.dependency_injection.container_factory import build_container
from pepelats.dependency_injection.service_collection import ServiceCollection


class Probe:
    pass


async def test_host_configs_resolve_from_context(
    service_config: ServiceConfig, environment: Environment
) -> None:
    collection = ServiceCollection(DynaconfConfiguration(FakeSettings()))

    provider = build_container(
        collection, service_config=service_config, environment=environment
    )

    assert await provider.get(ServiceConfig) is service_config
    assert await provider.get(Environment) is environment
    await provider.close()


async def test_extra_providers_are_registered(
    service_config: ServiceConfig, environment: Environment
) -> None:
    extra = Provider()
    extra.provide(source=lambda: Probe(), provides=Probe, scope=Scope.APP)
    collection = ServiceCollection(DynaconfConfiguration(FakeSettings()))

    provider = build_container(
        collection,
        service_config=service_config,
        environment=environment,
        extra_providers=[extra],
    )

    assert isinstance(await provider.get(Probe), Probe)
    await provider.close()
