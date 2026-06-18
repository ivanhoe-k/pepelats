"""Integration tests for complex appsettings merge shapes.

Covers nested sections, dict fields, array fields, mixed-case overlays, and env
overrides — the cases flat scalar tests do not exercise.
"""

import json
from pathlib import Path

import pytest

from pepelats.configuration import load_configuration
from pepelats.hosting.host_bootstrap import load_host_bootstrap
from pepelats.observability.logging_config import LoggingConfig

_COMPLEX_BASE = """\
environment = "Staging"

[service]
service_name = "test-service"
service_version = "2.3.0"

[logging]
log_level = "INFO"
sinks = ["console", "file"]
overrides = { "pepelats.hosting" = "WARNING", "uvicorn.access" = "ERROR" }

[logging.console]
json_logs = false

[logging.file]
dir = "logs"
file_name = "app.log"

[host]
bind = "0.0.0.0"
port = 9000

[observability]
otlp_endpoint = ""
"""

_STAGING_LOGGING_OVERLAY = """\
[logging]
log_level = "DEBUG"
sinks = ["console"]

[logging.console]
json_logs = true
"""


def _write_complex_base(directory: Path) -> Path:
    (directory / "appsettings.toml").write_text(_COMPLEX_BASE, encoding="utf-8")
    return directory


def _load_logging(config_dir: Path) -> LoggingConfig:
    loaded = load_configuration(config_dir)
    return loaded.configuration.get(LoggingConfig, section="logging")


def test_overlay_merges_nested_sections_and_preserves_unset_fields(tmp_path: Path) -> None:
    _write_complex_base(tmp_path)
    (tmp_path / "appsettings.Staging.toml").write_text(
        _STAGING_LOGGING_OVERLAY,
        encoding="utf-8",
    )

    logging = _load_logging(tmp_path)

    assert logging.log_level == "DEBUG"
    assert logging.console.json_logs is True
    assert logging.file.dir == "logs"
    assert logging.file.file_name == "app.log"
    assert logging.overrides == {
        "pepelats.hosting": "WARNING",
        "uvicorn.access": "ERROR",
    }


def test_overlay_array_merge_is_dynaconf_concat_not_replace(tmp_path: Path) -> None:
    _write_complex_base(tmp_path)
    (tmp_path / "appsettings.Staging.toml").write_text(
        _STAGING_LOGGING_OVERLAY,
        encoding="utf-8",
    )

    logging = _load_logging(tmp_path)

    assert logging.sinks == ["console", "file", "console"]


def test_mixed_case_overlay_filename_with_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base = _COMPLEX_BASE.replace('environment = "Staging"\n\n', "")
    (tmp_path / "appsettings.toml").write_text(base, encoding="utf-8")
    (tmp_path / "appsettings.my_suPeR_enV.json").write_text(
        json.dumps(
            {
                "logging": {
                    "log_level": "ERROR",
                    "sinks": ["console"],
                    "overrides": {"httpx": "WARNING"},
                },
                "logging.console": {"json_logs": True},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("ENVIRONMENT", "my_super_env")

    logging = _load_logging(tmp_path)

    assert logging.log_level == "ERROR"
    assert logging.sinks == ["console", "file", "console"]
    assert logging.console.json_logs is True
    assert logging.overrides == {
        "pepelats.hosting": "WARNING",
        "uvicorn.access": "ERROR",
        "httpx": "WARNING",
    }


def test_env_overrides_deep_nested_bool(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_complex_base(tmp_path)
    monkeypatch.setenv("LOGGING__CONSOLE__JSON_LOGS", "true")

    logging = _load_logging(tmp_path)

    assert logging.console.json_logs is True
    assert logging.log_level == "INFO"


def test_env_overrides_array_as_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_complex_base(tmp_path)
    monkeypatch.setenv("LOGGING__SINKS", '["console"]')

    logging = _load_logging(tmp_path)

    assert logging.sinks == ["console"]


def test_env_overrides_scalar_after_complex_file_merge(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_complex_base(tmp_path)
    (tmp_path / "appsettings.Staging.toml").write_text(
        _STAGING_LOGGING_OVERLAY,
        encoding="utf-8",
    )
    monkeypatch.setenv("HOST__PORT", "7777")

    loaded = load_configuration(tmp_path)
    bootstrap = load_host_bootstrap(loaded.configuration, environment=loaded.environment)

    assert bootstrap.host_config.server.port == 7777
    assert bootstrap.observability.enabled is False
