"""Bundle of service identity, logging config, and optional OTLP endpoint."""

from pydantic import BaseModel

from pepelats.configuration.service_config import ServiceConfig
from pepelats.observability.logging_config import LoggingConfig


class ObservabilityConfig(BaseModel):
    service: ServiceConfig
    logging: LoggingConfig
    otlp_endpoint: str | None = None


class _ObservabilitySection(BaseModel):
    otlp_endpoint: str | None = None
