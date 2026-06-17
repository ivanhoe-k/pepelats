"""Logs unhandled request exceptions before re-raising to the ASGI server.

Pure ASGI (no web framework), so it serves every host — generic Starlette or FastAPI.
"""

from starlette.types import ASGIApp, Receive, Scope, Send

from pepelats.observability import get_logger

logger = get_logger(__name__)


class ExceptionLoggingMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        try:
            await self.app(scope, receive, send)
        except Exception:
            if scope["type"] == "http":
                logger.error(
                    "unhandled_exception",
                    exc_info=True,
                    path=scope.get("path"),
                    method=scope.get("method"),
                )
            else:
                logger.error("unhandled_exception", exc_info=True)
            raise
