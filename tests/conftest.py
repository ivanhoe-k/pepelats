"""Shared fixtures and test doubles for the pepelats suite.

Target is pepelats only: nothing here imports socia_intelligence. Hosts and
services under test are synthetic, defined in the tests themselves.
"""

from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from doubles import FakeSettings

from pepelats.configuration import Configuration, Environment, ServiceConfig
from pepelats.configuration.configuration import DynaconfConfiguration
from pepelats.dependency_injection.container_factory import build_container
from pepelats.dependency_injection.service_collection import ServiceCollection
from pepelats.dependency_injection.service_provider import ServiceProvider
from pepelats.observability import shutdown_observability

# Console-only, local-only settings: no file sink (keeps tmp dirs clean) and no OTLP
# endpoint (no exporter touches the network during tests).
_APPSETTINGS = """\
[default]
environment = "local"

[default.service]
service_name = "test-service"
service_version = "1.0.0"

[default.logging]
log_level = "INFO"
sinks = ["console"]

[default.logging.console]
json_logs = false

[default.host]
bind = "127.0.0.1"
port = 8099

[default.observability]
otlp_endpoint = ""
"""


@pytest.fixture(autouse=True)
def reset_observability() -> Iterator[None]:
    """Tear down process-global OTel state after each test so it never bleeds.

    Observability is configured at host build time; a test that builds a host (or
    configures observability directly) leaves global providers set until shutdown.
    """
    yield
    shutdown_observability()


@pytest.fixture
def config_dir(tmp_path: Path) -> Path:
    """A config directory with a minimal, console-only ``appsettings.toml``."""
    (tmp_path / "appsettings.toml").write_text(_APPSETTINGS, encoding="utf-8")
    return tmp_path


@pytest.fixture
def fake_configuration() -> Configuration:
    return DynaconfConfiguration(FakeSettings())


@pytest.fixture
def service_config() -> ServiceConfig:
    return ServiceConfig(
        service_name="test-service",
        service_version="1.0.0",
        instance_id="instance-1",
    )


@pytest.fixture
def environment() -> Environment:
    return Environment(name="local")


@pytest.fixture
def build_provider(
    fake_configuration: Configuration,
    service_config: ServiceConfig,
    environment: Environment,
) -> Callable[[Callable[[ServiceCollection], object]], ServiceProvider]:
    """Build a ServiceProvider from a registration callback (no app config needed).

    The callback's return is ignored — registration methods return ``Self`` for
    chaining, so it is typed as ``object``.
    """

    def _build(
        configure: Callable[[ServiceCollection], object],
    ) -> ServiceProvider:
        collection = ServiceCollection(fake_configuration)
        configure(collection)
        return build_container(
            collection,
            service_config=service_config,
            environment=environment,
        )

    return _build
