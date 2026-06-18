"""Tests for section key handling: structural fields vs dict-valued data keys.

Logger names in logging.overrides are case-sensitive in Python's logging module.
Structural field names (port, json_logs) may arrive uppercased from Dynaconf env
injection. These tests pin both behaviors.
"""

from pathlib import Path

import pytest

from pepelats.configuration import load_configuration
from pepelats.hosting.server_config import ServerConfig
from pepelats.observability.logging_config import LoggingConfig

_BASE = """\
environment = "Staging"

[service]
service_name = "socia-core"
service_version = "2.3.0"

[logging]
log_level = "INFO"
sinks = ["console"]
overrides = { "MyApp.Worker" = "DEBUG", "Uvicorn.Access" = "ERROR" }

[host]
bind = "0.0.0.0"
port = 9000

[observability]
otlp_endpoint = ""
"""


def _write_base(directory: Path) -> None:
    (directory / "appsettings.toml").write_text(_BASE, encoding="utf-8")


def test_logging_override_dict_keys_preserve_logger_name_casing(tmp_path: Path) -> None:
    _write_base(tmp_path)

    loaded = load_configuration(tmp_path)
    logging = loaded.configuration.get(LoggingConfig, section="logging")

    assert logging.overrides == {
        "MyApp.Worker": "DEBUG",
        "Uvicorn.Access": "ERROR",
    }


def test_logging_override_keys_preserved_after_environment_overlay(tmp_path: Path) -> None:
    _write_base(tmp_path)
    (tmp_path / "appsettings.Staging.toml").write_text(
        '[logging]\nlog_level = "WARNING"\n',
        encoding="utf-8",
    )

    loaded = load_configuration(tmp_path)
    logging = loaded.configuration.get(LoggingConfig, section="logging")

    assert logging.log_level == "WARNING"
    assert logging.overrides == {
        "MyApp.Worker": "DEBUG",
        "Uvicorn.Access": "ERROR",
    }


def test_get_section_dict_preserves_dict_value_keys_without_lowercasing(
    tmp_path: Path,
) -> None:
    _write_base(tmp_path)

    loaded = load_configuration(tmp_path)
    logging_section = loaded.configuration.get_section_dict("logging")

    assert logging_section["overrides"] == {
        "MyApp.Worker": "DEBUG",
        "Uvicorn.Access": "ERROR",
    }


def test_env_injected_uppercase_field_names_bind_to_model(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_base(tmp_path)
    monkeypatch.setenv("HOST__PORT", "9001")

    loaded = load_configuration(tmp_path)
    server = loaded.configuration.get(ServerConfig, section="host")

    assert server.port == 9001
