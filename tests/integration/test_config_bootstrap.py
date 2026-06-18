"""Integration tests for the real config load path (Dynaconf -> typed host models).

These exercise load_configuration and load_host_bootstrap against on-disk TOML/JSON,
including overlay precedence — the one place real Dynaconf is in the loop.
"""

import json
from pathlib import Path

import pytest

from pepelats.configuration import (
    ConfigurationBootstrap,
    ConfigurationError,
    load_configuration,
)
from pepelats.hosting.host_bootstrap import HostBootstrap, load_host_bootstrap
from pepelats.observability.logging_config import LoggingConfig

_BASE = """\
environment = "Staging"

[service]
service_name = "test-service"
service_version = "2.3.0"

[logging]
log_level = "INFO"
sinks = ["console"]

[host]
bind = "0.0.0.0"
port = 9000

[observability]
otlp_endpoint = ""
"""

_LOCAL = """\
[observability]
enabled = true
otlp_endpoint = "http://localhost:4318"
"""


def _write(directory: Path, base: str, local: str | None = None) -> Path:
    (directory / "appsettings.toml").write_text(base, encoding="utf-8")
    if local is not None:
        (directory / "appsettings.Local.toml").write_text(local, encoding="utf-8")
    return directory


def _load_bootstrap(
    config_dir: Path,
    *,
    environment: str | None = None,
) -> HostBootstrap:
    loaded = load_configuration(config_dir, environment=environment)
    return load_host_bootstrap(loaded.configuration, environment=loaded.environment)


def test_load_configuration_reads_a_typed_section(tmp_path: Path) -> None:
    loaded = load_configuration(_write(tmp_path, _BASE))

    logging = loaded.configuration.get(LoggingConfig, section="logging")

    assert logging.log_level == "INFO"
    assert logging.sinks == ["console"]
    assert loaded.environment.name == "Staging"


def test_local_settings_override_base(tmp_path: Path) -> None:
    base = _BASE.replace('environment = "Staging"\n\n', 'environment = "local"\n\n')
    bootstrap = _load_bootstrap(_write(tmp_path, base, _LOCAL))

    assert bootstrap.environment.name == "local"
    assert bootstrap.observability.enabled is True
    assert bootstrap.observability.otlp_endpoint == "http://localhost:4318"


def test_staging_overlay_does_not_merge_local_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    _write(tmp_path, _BASE, _LOCAL)

    bootstrap = _load_bootstrap(tmp_path)

    assert bootstrap.environment.name == "Staging"
    assert bootstrap.observability.enabled is False
    assert bootstrap.observability.otlp_endpoint == ""


def test_bootstrap_maps_sections_to_typed_models(tmp_path: Path) -> None:
    bootstrap = _load_bootstrap(_write(tmp_path, _BASE))

    assert bootstrap.service_config.service_name == "test-service"
    assert bootstrap.service_config.service_version == "2.3.0"
    assert bootstrap.service_config.instance_id
    assert bootstrap.host_config.server.port == 9000
    assert bootstrap.host_config.shutdown_timeout_seconds == 10.0
    assert bootstrap.observability.export_timeout_seconds == 3.0


def test_bootstrap_reads_export_timeout_override(tmp_path: Path) -> None:
    base = _BASE.replace(
        '[observability]\notlp_endpoint = ""\n',
        '[observability]\notlp_endpoint = ""\nexport_timeout_seconds = 3.5\n',
    )

    bootstrap = _load_bootstrap(_write(tmp_path, base))

    assert bootstrap.observability.export_timeout_seconds == 3.5


def test_enabled_without_endpoint_is_rejected(tmp_path: Path) -> None:
    base = _BASE.replace(
        '[observability]\notlp_endpoint = ""\n',
        '[observability]\nenabled = true\notlp_endpoint = ""\n',
    )

    with pytest.raises(ConfigurationError):
        _load_bootstrap(_write(tmp_path, base))


def test_bootstrap_generates_a_unique_instance_id(tmp_path: Path) -> None:
    loaded = load_configuration(_write(tmp_path, _BASE))

    first = load_host_bootstrap(
        loaded.configuration,
        environment=loaded.environment,
    ).service_config.instance_id
    second = load_host_bootstrap(
        loaded.configuration,
        environment=loaded.environment,
    ).service_config.instance_id

    assert first != second


def test_load_configuration_from_json_base_file(tmp_path: Path) -> None:
    (tmp_path / "appsettings.json").write_text(
        json.dumps(
            {
                "environment": "Local",
                "service": {
                    "service_name": "json-service",
                    "service_version": "1.2.3",
                },
                "logging": {"log_level": "INFO", "sinks": ["console"]},
                "host": {"bind": "0.0.0.0", "port": 9000},
                "observability": {"otlp_endpoint": ""},
            }
        ),
        encoding="utf-8",
    )

    bootstrap = _load_bootstrap(tmp_path)

    assert bootstrap.environment.name == "Local"
    assert bootstrap.service_config.service_name == "json-service"
    assert bootstrap.host_config.server.port == 9000


def test_environment_overlay_merges_when_base_selects_environment(tmp_path: Path) -> None:
    _write(tmp_path, _BASE)
    (tmp_path / "appsettings.Staging.toml").write_text(
        "[host]\nport = 8080\n",
        encoding="utf-8",
    )

    bootstrap = _load_bootstrap(tmp_path)

    assert bootstrap.environment.name == "Staging"
    assert bootstrap.host_config.server.port == 8080


def test_environment_override_selects_overlay_file(tmp_path: Path) -> None:
    _write(tmp_path, _BASE)
    (tmp_path / "appsettings.Production.toml").write_text(
        "[host]\nport = 8080\n",
        encoding="utf-8",
    )

    bootstrap = _load_bootstrap(tmp_path, environment="Production")

    assert bootstrap.environment.name == "Production"
    assert bootstrap.host_config.server.port == 8080


def test_environment_variable_overrides_base_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write(tmp_path, _BASE)
    (tmp_path / "appsettings.Production.toml").write_text(
        "[host]\nport = 8080\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("ENVIRONMENT", "Production")

    bootstrap = _load_bootstrap(tmp_path)

    assert bootstrap.environment.name == "Production"
    assert bootstrap.host_config.server.port == 8080


def test_environment_variable_overrides_host_port_after_file_merge(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write(tmp_path, _BASE)
    monkeypatch.setenv("HOST__PORT", "7777")

    bootstrap = _load_bootstrap(tmp_path)

    assert bootstrap.host_config.server.port == 7777


def test_environment_variable_overrides_host_shutdown_timeout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write(tmp_path, _BASE)
    monkeypatch.setenv("HOST__SHUTDOWN_TIMEOUT_SECONDS", "15.5")

    bootstrap = _load_bootstrap(tmp_path)

    assert bootstrap.host_config.shutdown_timeout_seconds == 15.5


def test_default_environment_is_local_when_base_omits_environment_key(
    tmp_path: Path,
) -> None:
    base = _BASE.replace('environment = "Staging"\n\n', "")
    _write(tmp_path, base)

    bootstrap = _load_bootstrap(tmp_path)

    assert bootstrap.environment.name == "Local"


def test_missing_base_appsettings_raises_configuration_error(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError, match="No base appsettings file"):
        load_configuration(tmp_path)


def test_load_configuration_returns_bootstrap_pair(tmp_path: Path) -> None:
    loaded = load_configuration(_write(tmp_path, _BASE))

    assert isinstance(loaded, ConfigurationBootstrap)
    assert loaded.environment.name == "Staging"


def test_local_environment_name_is_preserved_from_base(tmp_path: Path) -> None:
    base = _BASE.replace('environment = "Staging"\n\n', 'environment = "local"\n\n')
    _write(tmp_path, base)
    (tmp_path / "appsettings.local.toml").write_text(
        "[host]\nport = 8099\n",
        encoding="utf-8",
    )

    bootstrap = _load_bootstrap(tmp_path)

    assert bootstrap.environment.name == "local"
    assert bootstrap.host_config.server.port == 8099


def test_custom_environment_overlay_matches_mixed_case_filename(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base = _BASE.replace('environment = "Staging"\n\n', "")
    _write(tmp_path, base)
    (tmp_path / "appsettings.my_suPeR_enV.json").write_text(
        json.dumps({"host": {"port": 8099}}),
        encoding="utf-8",
    )
    monkeypatch.setenv("ENVIRONMENT", "my_super_env")

    bootstrap = _load_bootstrap(tmp_path)

    assert bootstrap.environment.name == "my_super_env"
    assert bootstrap.host_config.server.port == 8099
