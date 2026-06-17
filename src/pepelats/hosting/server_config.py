"""Uvicorn bind address and port."""

from pydantic import BaseModel, Field


class ServerConfig(BaseModel):
    # Defaults target containerized deployment, where binding all interfaces is
    # expected. Override `bind` to "127.0.0.1" for local-only exposure.
    bind: str = Field(default="0.0.0.0")  # noqa: S104
    port: int = Field(default=8090, ge=1, le=65535)
