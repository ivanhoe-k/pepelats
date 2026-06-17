"""Transport-agnostic host lifecycle: start hosted services, run, tear down in order.

Owns the startup/shutdown sequence that every host shares, independent of any web
framework. Web adapters (FastAPI lifespan, future Starlette host) wrap this; it
never imports a transport.

Teardown order is invariant: stop hosted services -> container.close() (dispose
APP-scoped resources) -> shutdown_observability().
"""

import asyncio
from collections.abc import AsyncIterator, Iterable
from contextlib import asynccontextmanager

from pepelats.dependency_injection import ServiceProvider
from pepelats.hosting.background_service import BackgroundService
from pepelats.hosting.hosted_services import HostedServices
from pepelats.observability import get_logger, shutdown_observability

_logger = get_logger(__name__)


@asynccontextmanager
async def run_host_lifecycle(
    *,
    container: ServiceProvider,
    hosted_service_types: Iterable[type[BackgroundService]] = (),
    shutdown_timeout_seconds: float = 10.0,
) -> AsyncIterator[None]:
    """Start hosted services, yield for the duration of the host, then tear down.

    The caller does its work (serving requests, app-supplied lifespan) inside the
    yielded scope. On exit, hosted services stop first, then the container and
    observability are finalized.
    """
    # Background services are resolved from the container like any other service,
    # so their constructor dependencies are injected. Resolution happens here, in
    # the running loop, so async resources are entered now and finalized when the
    # container closes — last, after every service has stopped, so nothing is torn
    # down while still in use.
    hosted_services = HostedServices()
    try:
        # Inside the try: a failure resolving a service (or a duplicate name) must
        # still dispose the container and flush observability, since earlier APP
        # resources may already be constructed.
        for service_type in hosted_service_types:
            hosted_services.add(await container.get(service_type))

        async with _hosted_services_scope(hosted_services, shutdown_timeout_seconds):
            yield
    finally:
        # After hosted services stop: dispose APP-scoped resources, then flush OTel.
        await container.close()
        shutdown_observability()


@asynccontextmanager
async def _hosted_services_scope(
    services: Iterable[BackgroundService],
    shutdown_timeout_seconds: float,
) -> AsyncIterator[None]:
    service_list = list(services)
    if not service_list:
        yield
        return

    # One task per service, sharing a single stopping event for coordinated shutdown.
    stopping = asyncio.Event()
    tasks = [
        asyncio.create_task(service.start(stopping), name=service.name)
        for service in service_list
    ]
    try:
        yield
    finally:
        stopping.set()
        await _stop_hosted_services(tasks, shutdown_timeout_seconds)


async def _stop_hosted_services(
    tasks: list[asyncio.Task[None]],
    shutdown_timeout_seconds: float,
) -> None:
    # Give services until the timeout to exit on their own after stopping is set.
    try:
        await asyncio.wait_for(
            asyncio.gather(*tasks, return_exceptions=True),
            timeout=shutdown_timeout_seconds,
        )
    except TimeoutError:
        # A service ignored stopping or is stuck; cancel so the process can exit.
        _logger.warning(
            "hosted_services_shutdown_timeout",
            timeout_seconds=shutdown_timeout_seconds,
        )
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
