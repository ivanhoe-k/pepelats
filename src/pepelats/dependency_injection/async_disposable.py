"""Lifecycle contract for services that own something to release on shutdown."""

from abc import ABC, abstractmethod


class AsyncDisposable(ABC):
    """A service that must release resources when the container tears down.

    Implement this on any service that owns a connection, client, socket, or
    similar. Register it like any other service —
    ``add_singleton``/``add_scoped``/``add_transient`` — and the container calls
    ``dispose`` once nothing depends on it. There is no separate "resource"
    registration: disposal is detected from this contract.
    """

    @abstractmethod
    async def dispose(self) -> None: ...
