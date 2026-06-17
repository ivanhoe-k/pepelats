"""Long-running worker tied to the app lifetime.

Register with ``ServiceCollection.add_hosted_service``; the host runs ``start``
in its own task and signals shutdown via ``stopping``. Subclasses implement
only ``execute_async`` — lifecycle and logging stay here.
"""

import asyncio
from abc import ABC, abstractmethod

from pepelats.observability import get_logger

_logger = get_logger(__name__)


class BackgroundService(ABC):
    @property
    def name(self) -> str:
        # Used in logs and to reject duplicate registrations. Override when one
        # class runs as several workers (e.g. one per queue) to keep logs apart.
        return type(self).__name__

    async def start(self, stopping: asyncio.Event) -> None:
        # Host-owned task; returns once execute_async observes stopping.
        _logger.info("background_service_starting", service=self.name)
        try:
            await self.execute_async(stopping)
        except asyncio.CancelledError:
            # Host cancelled us past the shutdown timeout; re-raise so the task
            # is marked cancelled, not swallowed.
            raise
        except Exception:
            # Non-fatal: one worker must not take down the host or its siblings.
            _logger.exception("background_service_crashed", service=self.name)
        finally:
            _logger.info("background_service_stopped", service=self.name)

    @abstractmethod
    async def execute_async(self, stopping: asyncio.Event) -> None:
        # Must return promptly once stopping is set, else shutdown blocks until
        # the host's timeout forces cancellation. Race long waits against
        # stopping.wait() instead of sleeping blindly.
        ...
