"""ServiceCollection — the registration facade over Dishka.

The only place app-facing code touches DI. Methods name a service's lifetime directly
(add_singleton/scoped/transient/factory/...). Registrations accumulate on a Dishka
Provider that container_factory turns into a container.
"""

from __future__ import annotations

import inspect
from collections.abc import AsyncIterator, Callable
from typing import TYPE_CHECKING, Self

from dishka import Provider, Scope
from pydantic import BaseModel

from pepelats.configuration import Configuration
from pepelats.dependency_injection.async_disposable import AsyncDisposable

if TYPE_CHECKING:
    from pepelats.hosting.background_service import BackgroundService


class ServiceCollection:
    def __init__(self, configuration: Configuration) -> None:
        self._configuration = configuration
        self._provider = Provider()
        self._hosted_service_types: list[type[BackgroundService]] = []

    def add_singleton[T](
        self,
        interface: type[T],
        impl: type[T] | None = None,
    ) -> Self:
        self._register(interface, impl, scope=Scope.APP)
        return self

    def add_scoped[T](
        self,
        interface: type[T],
        impl: type[T] | None = None,
    ) -> Self:
        self._register(interface, impl, scope=Scope.REQUEST)
        return self

    def add_transient[T](
        self,
        interface: type[T],
        impl: type[T] | None = None,
    ) -> Self:
        self._register(interface, impl, scope=Scope.REQUEST, cache=False)
        return self

    def _register[T](
        self,
        interface: type[T],
        impl: type[T] | None,
        *,
        scope: Scope,
        cache: bool = True,
    ) -> None:
        # AsyncDisposable services are finalized like any other dependency: the
        # container constructs them with injected ctor args and calls dispose()
        # when their scope ends. Dishka only finalizes generators, so we wrap the
        # type in one that mirrors its constructor signature for injection.
        concrete = impl or interface
        if inspect.iscoroutinefunction(concrete.__init__):
            msg = (
                f"{concrete.__name__}.__init__ must be synchronous for DI construction"
            )
            raise TypeError(msg)
        source: type[T] | Callable[..., AsyncIterator[T]] = concrete
        if issubclass(concrete, AsyncDisposable):
            source = _disposable_resource(concrete)
        self._provider.provide(
            source=source,
            provides=interface,
            scope=scope,
            cache=cache,
        )

    def add_factory[T](
        self,
        interface: type[T],
        factory: Callable[..., T],
    ) -> Self:
        # APP-scoped (singleton): the factory runs once, its dependencies injected.
        # Unlike add_singleton, the AsyncDisposable contract is not auto-detected
        # here — to release a resource, pass an (async) generator factory that
        # yields the instance and cleans up after; Dishka finalizes it on close.
        self._provider.provide(
            source=factory,
            provides=interface,
            scope=Scope.APP,
        )
        return self

    def add_configuration[TConfig: BaseModel](
        self,
        model: type[TConfig],
        *,
        section: str | None = None,
    ) -> Self:
        # Validation runs inside Configuration.get() via Pydantic model_validate.
        instance = self._configuration.get(model, section=section)
        self._provider.provide(
            source=lambda: instance,
            provides=model,
            scope=Scope.APP,
        )
        return self

    def add_hosted_service(self, service: type[BackgroundService]) -> Self:
        # A background service is resolved like any other service: its constructor
        # dependencies are injected. We register the type here and record it so
        # the host can resolve and run it for the app lifetime.
        self._provider.provide(source=service, provides=service, scope=Scope.APP)
        self._hosted_service_types.append(service)
        return self

    @property
    def hosted_service_types(self) -> list[type[BackgroundService]]:
        return list(self._hosted_service_types)


def registration_provider(collection: ServiceCollection) -> Provider:
    """Package-internal: Dishka provider built from collection registrations."""
    return collection._provider


def _disposable_resource[T: AsyncDisposable](
    impl: type[T],
) -> Callable[..., AsyncIterator[T]]:
    """Wrap a disposable type in a generator Dishka can finalize.

    The generator re-exposes the type's constructor parameters so Dishka injects
    them as usual, yields the instance, then calls dispose() on scope exit.
    """

    async def resource(*args: object, **kwargs: object) -> AsyncIterator[T]:
        instance = impl(*args, **kwargs)
        try:
            yield instance
        finally:
            await instance.dispose()

    parameters = [
        parameter
        for name, parameter in inspect.signature(impl.__init__).parameters.items()
        if name != "self"
    ]
    resource.__signature__ = inspect.Signature(parameters)  # type: ignore[attr-defined]
    resource.__annotations__ = {
        parameter.name: parameter.annotation for parameter in parameters
    }
    # Runtime-only: the concrete yielded type for Dishka; impl is a value here.
    resource.__annotations__["return"] = AsyncIterator[impl]  # type: ignore[valid-type]
    return resource
