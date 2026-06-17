"""The runtime DI container abstraction and its adapter.

Core depends on the `ServiceProvider` ABC, never on the DI engine directly: resolve a
dependency (`get`), open a per-unit-of-work scope (`enter_scope`), or dispose the
container (`close`). Swapping the engine means writing one new adapter — nothing else
in core changes.

`enter_scope` lets non-request code (message handlers, CLI, cron) wrap each unit of work
in its own scope, so scoped services live and dispose per task instead of being pulled
from the root container as a service locator.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Mapping
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import Any

from dishka import AsyncContainer


class ServiceProvider(ABC):
    @abstractmethod
    async def get[T](self, service_type: type[T]) -> T:
        """Resolve a service from the current scope."""

    @abstractmethod
    def enter_scope(
        self, context: Mapping[Any, Any] | None = None
    ) -> AbstractAsyncContextManager[ServiceProvider]:
        """Open a nested scope (a unit of work), yielding its provider.

        `context` seeds values resolvable within the scope (e.g. the HTTP request).

        `async with provider.enter_scope() as scope: ...`
        """

    @abstractmethod
    async def close(self) -> None:
        """Dispose this scope and the resources it owns."""


class DishkaServiceProvider(ServiceProvider):
    """`ServiceProvider` backed by a Dishka `AsyncContainer`."""

    def __init__(self, container: AsyncContainer) -> None:
        self._container = container

    async def get[T](self, service_type: type[T]) -> T:
        service: T = await self._container.get(service_type)
        return service

    @asynccontextmanager
    async def enter_scope(
        self, context: Mapping[Any, Any] | None = None
    ) -> AsyncIterator[ServiceProvider]:
        async with self._container(dict(context) if context else None) as scoped:
            yield DishkaServiceProvider(scoped)

    async def close(self) -> None:
        await self._container.close()
