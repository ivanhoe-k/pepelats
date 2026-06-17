"""Typed [host] section: server bind/port and shutdown behavior."""

from pydantic import BaseModel, Field

from pepelats.hosting.server_config import ServerConfig


class HostConfig(BaseModel):
    server: ServerConfig = Field(default_factory=ServerConfig)
    # Grace period for background services to stop before the host cancels them.
    shutdown_timeout_seconds: float = Field(default=10.0, gt=0)
