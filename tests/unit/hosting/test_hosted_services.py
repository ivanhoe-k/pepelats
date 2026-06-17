"""Unit tests for HostedServices registration semantics."""

import asyncio

import pytest

from pepelats.hosting.background_service import BackgroundService
from pepelats.hosting.hosted_services import HostedServices


class _Service(BackgroundService):
    def __init__(self, name: str) -> None:
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    async def execute_async(self, stopping: asyncio.Event) -> None:
        await stopping.wait()


def test_add_preserves_order_and_length() -> None:
    services = HostedServices()
    first = _Service("a")
    second = _Service("b")

    services.add(first)
    services.add(second)

    assert len(services) == 2
    assert list(services) == [first, second]


def test_add_rejects_duplicate_name() -> None:
    services = HostedServices()
    services.add(_Service("worker"))

    with pytest.raises(ValueError, match="already registered"):
        services.add(_Service("worker"))
