"""Integration tests for the real config load path (Dynaconf -> typed host models).

These exercise load_configuration and load_host_bootstrap against on-disk TOML,
including local-override precedence — the one place real Dynaconf is in the loop.
"""

from pathlib import Path

import pytest

from pepelats.configuration import ConfigurationError, load_configuration
from pepelats.hosting.host_bootstrap import load_host_bootstrap
from pepelats.observability.logging_config import LoggingConfig

_BASE = """\
[default]
environment = "staging"

[default.service]
service_name = "socia-core"
service_version = "2.3.0"

[default.logging]
log_level = "INFO"
sinks = ["console"]

[default.host]
bind = "0.0.0.0"
port = 9000

[default.observability]
otlp_endpoint = ""
"""

_LOCAL = """\
[default]
environment = "local"

[default.observability]
enabled = true
otlp_endpoint = "http://localhost:4318"
"""


def _write(directory: Path, base: str, local: str | None = None) -> Path:
    (directory / "appsettings.toml").write_text(base, encoding="utf-8")
    if local is not None:
        (directory / "appsettings.local.toml").write_text(local, encoding="utf-8")
    return directory


def test_load_configuration_reads_a_typed_section(tmp_path: Path) -> None:
    configuration = load_configuration(_write(tmp_path, _BASE))

    logging = configuration.get(LoggingConfig, section="logging")

    assert logging.log_level == "INFO"
    assert logging.sinks == ["console"]


def test_local_settings_override_base(tmp_path: Path) -> None:
    configuration = load_configuration(_write(tmp_path, _BASE, _LOCAL))

    bootstrap = load_host_bootstrap(configuration)

    assert bootstrap.environment.name == "local"
    assert bootstrap.observability.enabled is True
    assert bootstrap.observability.otlp_endpoint == "http://localhost:4318"


def test_bootstrap_maps_sections_to_typed_models(tmp_path: Path) -> None:
    configuration = load_configuration(_write(tmp_path, _BASE))

    bootstrap = load_host_bootstrap(configuration)

    assert bootstrap.service_config.service_name == "socia-core"
    assert bootstrap.service_config.service_version == "2.3.0"
    assert bootstrap.service_config.instance_id  # generated per load
    assert bootstrap.host_config.server.port == 9000
    assert bootstrap.host_config.shutdown_timeout_seconds == 10.0
    assert bootstrap.observability.export_timeout_seconds == 3.0


def test_bootstrap_reads_export_timeout_override(tmp_path: Path) -> None:
    base = _BASE.replace(
        '[default.observability]\notlp_endpoint = ""\n',
        '[default.observability]\notlp_endpoint = ""\nexport_timeout_seconds = 3.5\n',
    )

    bootstrap = load_host_bootstrap(load_configuration(_write(tmp_path, base)))

    assert bootstrap.observability.export_timeout_seconds == 3.5


def test_enabled_without_endpoint_is_rejected(tmp_path: Path) -> None:
    base = _BASE.replace(
        '[default.observability]\notlp_endpoint = ""\n',
        '[default.observability]\nenabled = true\notlp_endpoint = ""\n',
    )

    with pytest.raises(ConfigurationError):
        load_host_bootstrap(load_configuration(_write(tmp_path, base)))


def test_bootstrap_generates_a_unique_instance_id(tmp_path: Path) -> None:
    configuration = load_configuration(_write(tmp_path, _BASE))

    first = load_host_bootstrap(configuration).service_config.instance_id
    second = load_host_bootstrap(configuration).service_config.instance_id

    assert first != second
