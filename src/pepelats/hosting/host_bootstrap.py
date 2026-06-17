"""Single load path: configuration -> environment, service, host config, observability.

Maps TOML sections to typed host models. The generic reader lives on Configuration;
these are the host-specific bindings (which sections, how they nest).
"""

import uuid
from dataclasses import dataclass

from pepelats.configuration import (
    Configuration,
    Environment,
    ServiceConfig,
)
from pepelats.hosting.host_config import HostConfig
from pepelats.hosting.server_config import ServerConfig
from pepelats.observability.logging_config import LoggingConfig
from pepelats.observability.observability_config import (
    ObservabilityConfig,
    _ObservabilitySection,
)


@dataclass(frozen=True, slots=True)
class HostBootstrap:
    configuration: Configuration
    environment: Environment
    service_config: ServiceConfig
    host_config: HostConfig
    observability: ObservabilityConfig


def load_host_bootstrap(configuration: Configuration) -> HostBootstrap:
    service = _load_service_config(configuration)

    return HostBootstrap(
        configuration=configuration,
        environment=_load_environment(configuration),
        service_config=service,
        host_config=_load_host_config(configuration),
        observability=_load_observability_config(configuration, service=service),
    )


def _load_environment(configuration: Configuration) -> Environment:
    return Environment(name=configuration.get_value("environment", default="local"))


def _load_service_config(configuration: Configuration) -> ServiceConfig:
    service = configuration.get_section_dict("service")
    return ServiceConfig.model_validate(
        {
            **service,
            "instance_id": str(uuid.uuid4()),
        }
    )


def _load_host_config(configuration: Configuration) -> HostConfig:
    host_dict = configuration.get_section_dict("host")
    # ServerConfig owns its own keys (bind/port); shutdown lives on HostConfig.
    return HostConfig(
        server=ServerConfig.model_validate(host_dict),
        shutdown_timeout_seconds=host_dict.get("shutdown_timeout_seconds", 10.0),
    )


def _load_observability_config(
    configuration: Configuration,
    *,
    service: ServiceConfig,
) -> ObservabilityConfig:
    observability = configuration.try_get(
        _ObservabilitySection,
        section="observability",
    )
    # Empty-string / env-fallback normalization is centralized in
    # tracing.resolve_otlp_endpoint, called during configure_observability.
    otlp_endpoint = observability.otlp_endpoint if observability else None

    return ObservabilityConfig(
        service=service,
        logging=configuration.get(LoggingConfig, section="logging"),
        otlp_endpoint=otlp_endpoint,
    )
