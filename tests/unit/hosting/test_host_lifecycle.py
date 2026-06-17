"""Unit tests for run_host_lifecycle: startup, teardown order, and failure paths.

A recording ServiceProvider double stands in for the container so we can assert the
teardown sequence without a real DI engine; `shutdown_observability` is patched to the
same recorder to lock its position in the order.
"""

import asyncio
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from typing import Any, cast

import pytest

from pepelats.dependency_injection import ServiceProvider
from pepelats.hosting import host_lifecycle
from pepelats.hosting.background_service import BackgroundService
from pepelats.hosting.host_lifecycle import run_host_lifecycle


class RecordingProvider(ServiceProvider):
    """Resolves pre-built instances and records its own close()."""

    def __init__(
        self, events: list[str], instances: Mapping[type[Any], Any] | None = None
    ) -> None:
        self._events = events
        self._instances = dict(instances or {})

    async def get[T](self, service_type: type[T]) -> T:
        return cast(T, self._instances[service_type])

    @asynccontextmanager
    async def enter_scope(
        self, context: Mapping[Any, Any] | None = None
    ) -> AsyncIterator[ServiceProvider]:
        yield self

    async def close(self) -> None:
        self._events.append("container_closed")


class FailingProvider(RecordingProvider):
    async def get[T](self, service_type: type[T]) -> T:
        raise RuntimeError("resolution failed")


class RecordingService(BackgroundService):
    def __init__(self, events: list[str], name: str = "worker") -> None:
        self._events = events
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    async def execute_async(self, stopping: asyncio.Event) -> None:
        await stopping.wait()
        self._events.append(f"stopped:{self._name}")


class StuckService(BackgroundService):
    async def execute_async(self, stopping: asyncio.Event) -> None:
        await asyncio.sleep(3600)  # ignores stopping, forcing a cancel at timeout


class CrashingService(BackgroundService):
    async def execute_async(self, stopping: asyncio.Event) -> None:
        raise RuntimeError("worker crashed")


@pytest.fixture(autouse=True)
def record_observability_shutdown(
    monkeypatch: pytest.MonkeyPatch, events: list[str]
) -> None:
    monkeypatch.setattr(
        host_lifecycle,
        "shutdown_observability",
        lambda: events.append("observability_shutdown"),
    )


@pytest.fixture
def events() -> list[str]:
    return []


async def test_teardown_runs_services_then_container_then_observability(
    events: list[str],
) -> None:
    service = RecordingService(events)
    container = RecordingProvider(events, {RecordingService: service})

    async with run_host_lifecycle(
        container=container, hosted_service_types=[RecordingService]
    ):
        events.append("serving")

    assert events == [
        "serving",
        "stopped:worker",
        "container_closed",
        "observability_shutdown",
    ]


async def test_runs_without_hosted_services(events: list[str]) -> None:
    container = RecordingProvider(events)

    async with run_host_lifecycle(container=container):
        events.append("serving")

    assert events == ["serving", "container_closed", "observability_shutdown"]


async def test_startup_resolution_failure_still_tears_down(events: list[str]) -> None:
    container = FailingProvider(events)

    with pytest.raises(RuntimeError):
        async with run_host_lifecycle(
            container=container, hosted_service_types=[RecordingService]
        ):
            events.append("serving")

    assert events == ["container_closed", "observability_shutdown"]


async def test_duplicate_service_name_rejected_and_torn_down(
    events: list[str],
) -> None:
    container = RecordingProvider(
        events,
        {
            RecordingService: RecordingService(events, name="dup"),
            CrashingService: RecordingService(events, name="dup"),
        },
    )

    with pytest.raises(ValueError, match="already registered"):
        async with run_host_lifecycle(
            container=container,
            hosted_service_types=[RecordingService, CrashingService],
        ):
            events.append("serving")

    assert "container_closed" in events
    assert "observability_shutdown" in events


async def test_stuck_service_is_cancelled_at_timeout(events: list[str]) -> None:
    container = RecordingProvider(events, {StuckService: StuckService()})

    async with run_host_lifecycle(
        container=container,
        hosted_service_types=[StuckService],
        shutdown_timeout_seconds=0.05,
    ):
        events.append("serving")

    assert events[-2:] == ["container_closed", "observability_shutdown"]


async def test_crashing_service_does_not_take_down_host_or_siblings(
    events: list[str],
) -> None:
    sibling = RecordingService(events, name="sibling")
    container = RecordingProvider(
        events,
        {CrashingService: CrashingService(), RecordingService: sibling},
    )

    async with run_host_lifecycle(
        container=container,
        hosted_service_types=[CrashingService, RecordingService],
    ):
        events.append("serving")

    assert "serving" in events
    assert "stopped:sibling" in events
    assert events[-2:] == ["container_closed", "observability_shutdown"]
