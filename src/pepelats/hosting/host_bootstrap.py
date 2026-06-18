"""Single load path: configuration -> environment, service, host config, observability.

Maps configuration sections to typed host models. The generic reader lives on
`Configuration`; these are the host-specific bindings (which sections, how they
nest). The host environment name is resolved during configuration load and passed
in explicitly.
"""

import uuid
from dataclasses import dataclass

from pepelats.configuration import (
    Configuration,
    Environment,
    ServiceConfig,
)
from pepelats.configuration.section_coercion import read_section_field, validate_section
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


def load_host_bootstrap(
    configuration: Configuration,
    *,
    environment: Environment,
) -> HostBootstrap:
    service = _load_service_config(configuration)

    return HostBootstrap(
        configuration=configuration,
        environment=environment,
        service_config=service,
        host_config=_load_host_config(configuration),
        observability=_load_observability_config(configuration, service=service),
    )


def _load_service_config(configuration: Configuration) -> ServiceConfig:
    service = configuration.get_section_dict("service")
    return validate_section(
        ServiceConfig,
        {
            **service,
            "instance_id": str(uuid.uuid4()),
        },
    )


def _load_host_config(configuration: Configuration) -> HostConfig:
    host_dict = configuration.get_section_dict("host")
    # Flat [host] maps bind/port into ServerConfig; other HostConfig fields bind here.
    return HostConfig(
        server=validate_section(ServerConfig, host_dict),
        shutdown_timeout_seconds=read_section_field(
            host_dict,
            HostConfig,
            "shutdown_timeout_seconds",
            default=10.0,
        ),
    )


def _load_observability_config(
    configuration: Configuration,
    *,
    service: ServiceConfig,
) -> ObservabilityConfig:
    section = (
        configuration.try_get(_ObservabilitySection, section="observability")
        or _ObservabilitySection()
    )
    return ObservabilityConfig(
        service=service,
        logging=configuration.get(LoggingConfig, section="logging"),
        enabled=section.enabled,
        otlp_endpoint=section.otlp_endpoint,
        export_timeout_seconds=section.export_timeout_seconds,
    )
