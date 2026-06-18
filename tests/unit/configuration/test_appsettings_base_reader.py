"""Unit tests for reading the environment key from the base appsettings file."""

import json
from pathlib import Path

import pytest

from pepelats.configuration.appsettings_base_reader import read_environment_from_base
from pepelats.configuration.appsettings_environment import DEFAULT_ENVIRONMENT_NAME
from pepelats.configuration.errors import ConfigurationError


def test_returns_default_when_environment_key_is_missing(tmp_path: Path) -> None:
    base = tmp_path / "appsettings.toml"
    base.write_text("[service]\nname = \"demo\"\n", encoding="utf-8")

    assert (
        read_environment_from_base(base, default=DEFAULT_ENVIRONMENT_NAME)
        == DEFAULT_ENVIRONMENT_NAME
    )


def test_reads_environment_from_flat_toml(tmp_path: Path) -> None:
    base = tmp_path / "appsettings.toml"
    base.write_text('environment = "Staging"\n', encoding="utf-8")

    assert read_environment_from_base(base, default=DEFAULT_ENVIRONMENT_NAME) == "Staging"


def test_reads_environment_from_flat_json(tmp_path: Path) -> None:
    base = tmp_path / "appsettings.json"
    base.write_text(json.dumps({"environment": "Production"}), encoding="utf-8")

    assert read_environment_from_base(base, default=DEFAULT_ENVIRONMENT_NAME) == "Production"


def test_rejects_invalid_environment_value(tmp_path: Path) -> None:
    base = tmp_path / "appsettings.toml"
    base.write_text("environment = 1\n", encoding="utf-8")

    with pytest.raises(ConfigurationError, match="non-empty string"):
        read_environment_from_base(base, default=DEFAULT_ENVIRONMENT_NAME)


def test_rejects_invalid_toml(tmp_path: Path) -> None:
    base = tmp_path / "appsettings.toml"
    base.write_text("environment = \n", encoding="utf-8")

    with pytest.raises(ConfigurationError, match="Failed to parse"):
        read_environment_from_base(base, default=DEFAULT_ENVIRONMENT_NAME)
