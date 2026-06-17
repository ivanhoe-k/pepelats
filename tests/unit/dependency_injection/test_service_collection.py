"""Unit tests for ServiceCollection registration semantics.

Resolution is exercised through a real container (build_container) — we test our
registration/scoping contract, not Dishka internals.
"""

import asyncio
from collections.abc import Callable

import pytest
from doubles import FakeSettings, RecordingDisposable
from pydantic import BaseModel

from pepelats.configuration import Environment, ServiceConfig
from pepelats.configuration.configuration import DynaconfConfiguration
from pepelats.dependency_injection.container_factory import build_container
from pepelats.dependency_injection.service_collection import ServiceCollection
from pepelats.dependency_injection.service_provider import ServiceProvider
from pepelats.hosting.background_service import BackgroundService

BuildProvider = Callable[[Callable[[ServiceCollection], object]], ServiceProvider]


class Counter:
    pass


class Greeter:
    def greet(self) -> str:
        return "base"


class FriendlyGreeter(Greeter):
    def greet(self) -> str:
        return "friendly"


class Worker(BackgroundService):
    async def execute_async(self, stopping: asyncio.Event) -> None:
        await stopping.wait()


async def test_add_singleton_returns_same_instance(
    build_provider: BuildProvider,
) -> None:
    provider = build_provider(lambda services: services.add_singleton(Counter))

    first = await provider.get(Counter)
    second = await provider.get(Counter)

    assert first is second
    await provider.close()


async def test_add_singleton_maps_interface_to_impl(
    build_provider: BuildProvider,
) -> None:
    provider = build_provider(
        lambda services: services.add_singleton(Greeter, FriendlyGreeter)
    )

    resolved = await provider.get(Greeter)

    assert isinstance(resolved, FriendlyGreeter)
    await provider.close()


async def test_add_scoped_resolves_per_scope(build_provider: BuildProvider) -> None:
    provider = build_provider(lambda services: services.add_scoped(Counter))

    async with provider.enter_scope() as scope_a:
        first = await scope_a.get(Counter)
        same_scope = await scope_a.get(Counter)
    async with provider.enter_scope() as scope_b:
        other_scope = await scope_b.get(Counter)

    assert first is same_scope
    assert first is not other_scope
    await provider.close()


async def test_add_transient_resolves_new_each_time(
    build_provider: BuildProvider,
) -> None:
    provider = build_provider(lambda services: services.add_transient(Counter))

    async with provider.enter_scope() as scope:
        first = await scope.get(Counter)
        second = await scope.get(Counter)

    assert first is not second
    await provider.close()


async def test_add_factory_runs_once_and_caches(build_provider: BuildProvider) -> None:
    calls = 0

    def factory() -> Counter:
        nonlocal calls
        calls += 1
        return Counter()

    provider = build_provider(lambda services: services.add_factory(Counter, factory))

    first = await provider.get(Counter)
    second = await provider.get(Counter)

    assert first is second
    assert calls == 1
    await provider.close()


async def test_add_configuration_registers_validated_instance(
    service_config: ServiceConfig, environment: Environment
) -> None:
    class WidgetConfig(BaseModel):
        size: int

    configuration = DynaconfConfiguration(FakeSettings({"widget": {"size": 10}}))
    collection = ServiceCollection(configuration)
    collection.add_configuration(WidgetConfig)
    provider = build_container(
        collection, service_config=service_config, environment=environment
    )

    resolved = await provider.get(WidgetConfig)

    assert resolved.size == 10
    await provider.close()


async def test_singleton_disposable_disposed_on_close(
    build_provider: BuildProvider,
) -> None:
    provider = build_provider(
        lambda services: services.add_singleton(RecordingDisposable)
    )

    instance = await provider.get(RecordingDisposable)
    assert instance.disposed is False

    await provider.close()

    assert instance.disposed is True


async def test_scoped_disposable_disposed_on_scope_exit(
    build_provider: BuildProvider,
) -> None:
    provider = build_provider(lambda services: services.add_scoped(RecordingDisposable))

    async with provider.enter_scope() as scope:
        instance = await scope.get(RecordingDisposable)
        assert instance.disposed is False

    assert instance.disposed is True
    await provider.close()


def test_add_singleton_rejects_async_init() -> None:
    class AsyncInit:
        async def __init__(self) -> None:  # type: ignore[misc]
            ...

    collection = ServiceCollection(DynaconfConfiguration(FakeSettings()))

    with pytest.raises(TypeError):
        collection.add_singleton(AsyncInit)


def test_hosted_service_types_returns_copy() -> None:
    collection = ServiceCollection(DynaconfConfiguration(FakeSettings()))
    collection.add_hosted_service(Worker)

    snapshot = collection.hosted_service_types
    snapshot.clear()

    assert collection.hosted_service_types == [Worker]
