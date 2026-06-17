"""Registered background services the host starts on startup and stops on shutdown."""

from collections.abc import Iterator

from pepelats.hosting.background_service import BackgroundService


class HostedServices:
    def __init__(self) -> None:
        self._services: list[BackgroundService] = []
        self._names: set[str] = set()

    def add(self, service: BackgroundService) -> None:
        # Reject duplicate names: they make logs ambiguous and usually signal a
        # double registration. _names is an O(1) guard alongside the list.
        if service.name in self._names:
            msg = f"Background service '{service.name}' is already registered."
            raise ValueError(msg)
        self._names.add(service.name)
        self._services.append(service)

    def __iter__(self) -> Iterator[BackgroundService]:
        return iter(self._services)

    def __len__(self) -> int:
        return len(self._services)
