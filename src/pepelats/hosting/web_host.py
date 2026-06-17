"""Runnable web host — a Starlette app served by uvicorn.

The bare HTTP substrate, with no Web API framework attached. The FastAPI integration
layers on top; on its own it serves whatever routes/middleware the pipeline registered.

Lifecycle: observability is configured when the host is *built*; its teardown (and
hosted-service shutdown, container disposal) runs inside the ASGI lifespan, i.e. when
the host is *served* via `run()`. A host that is built but never served is not torn
down.
"""

import uvicorn
from starlette.applications import Starlette


class WebHost:
    def __init__(self, app: Starlette, *, bind: str, port: int) -> None:
        self._app = app
        self._bind = bind
        self._port = port

    @property
    def app(self) -> Starlette:
        """The assembled ASGI application (for embedding or ASGI test clients)."""
        return self._app

    def run(self) -> None:
        uvicorn.run(
            self._app,
            host=self._bind,
            port=self._port,
            reload=False,
            access_log=True,
        )
