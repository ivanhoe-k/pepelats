"""Bundle of service identity, logging config, and optional OTLP endpoint."""

from typing import Self

from pydantic import BaseModel, Field, model_validator

from pepelats.configuration import ConfigurationError
from pepelats.configuration.service_config import ServiceConfig
from pepelats.observability.logging_config import LoggingConfig

# Caps every OTLP export (runtime and the final flush on shutdown). With a dead
# collector this is what bounds how long teardown blocks before the host moves on.
# A healthy local collector answers in milliseconds; this is the dead-collector
# ceiling, kept low so shutdown stays snappy.
_DEFAULT_EXPORT_TIMEOUT_SECONDS = 3.0


class ObservabilityConfig(BaseModel):
    service: ServiceConfig
    logging: LoggingConfig
    enabled: bool = False
    otlp_endpoint: str | None = None
    export_timeout_seconds: float = Field(
        default=_DEFAULT_EXPORT_TIMEOUT_SECONDS, gt=0
    )

    @model_validator(mode="after")
    def _require_endpoint_when_enabled(self) -> Self:
        # enabled is the explicit switch; an empty endpoint while on is a config
        # mistake, not a silent "export off" — fail loud rather than guess.
        if self.enabled and not (self.otlp_endpoint or "").strip():
            msg = "observability.otlp_endpoint is required when enabled"
            raise ConfigurationError(msg)
        return self


class _ObservabilitySection(BaseModel):
    enabled: bool = False
    otlp_endpoint: str | None = None
    export_timeout_seconds: float = Field(
        default=_DEFAULT_EXPORT_TIMEOUT_SECONDS, gt=0
    )
