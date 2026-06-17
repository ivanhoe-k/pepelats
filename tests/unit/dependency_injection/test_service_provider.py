"""Unit tests for the ServiceProvider abstraction (Dishka adapter)."""

from collections.abc import Callable

from pepelats.dependency_injection.service_collection import ServiceCollection
from pepelats.dependency_injection.service_provider import ServiceProvider

BuildProvider = Callable[[Callable[[ServiceCollection], object]], ServiceProvider]


class Counter:
    pass


async def test_enter_scope_yields_a_distinct_provider(
    build_provider: BuildProvider,
) -> None:
    provider = build_provider(lambda services: services.add_scoped(Counter))

    async with provider.enter_scope() as scope:
        assert scope is not provider
        assert isinstance(await scope.get(Counter), Counter)

    await provider.close()


async def test_close_is_idempotent(build_provider: BuildProvider) -> None:
    provider = build_provider(lambda services: services.add_singleton(Counter))

    await provider.close()
    await provider.close()
