"""Unit tests for active environment resolution."""

import json
from pathlib import Path

import pytest

from pepelats.configuration.appsettings_environment import (
    DEFAULT_ENVIRONMENT_NAME,
    resolve_active_environment,
    validate_environment_name,
)


def _write_base(tmp_path: Path, *, environment: str | None = None) -> Path:
    base = tmp_path / "appsettings.toml"
    if environment is None:
        base.write_text("[service]\nname = \"demo\"\n", encoding="utf-8")
    else:
        base.write_text(f'environment = "{environment}"\n', encoding="utf-8")
    return base


def test_defaults_to_local_when_base_has_no_environment_key(tmp_path: Path) -> None:
    base = _write_base(tmp_path)

    assert resolve_active_environment(base) == DEFAULT_ENVIRONMENT_NAME


def test_reads_environment_from_base_file(tmp_path: Path) -> None:
    base = _write_base(tmp_path, environment="Staging")

    assert resolve_active_environment(base) == "Staging"


def test_environment_variable_overrides_base_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base = _write_base(tmp_path, environment="Staging")
    monkeypatch.setenv("ENVIRONMENT", "Production")

    assert resolve_active_environment(base) == "Production"


def test_explicit_override_wins_over_environment_variable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base = _write_base(tmp_path, environment="Staging")
    monkeypatch.setenv("ENVIRONMENT", "Production")

    assert resolve_active_environment(base, override="Testing") == "Testing"


def test_json_base_file_is_supported_for_environment_resolution(tmp_path: Path) -> None:
    base = tmp_path / "appsettings.json"
    base.write_text(json.dumps({"environment": "Development"}), encoding="utf-8")

    assert resolve_active_environment(base) == "Development"


def test_validate_environment_name_preserves_author_casing() -> None:
    assert validate_environment_name("  my_suPeR_enV  ") == "my_suPeR_enV"


def test_environment_name_is_not_rewritten_to_title_case(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base = _write_base(tmp_path, environment="local")
    monkeypatch.setenv("ENVIRONMENT", "my_super_env")

    assert resolve_active_environment(base) == "my_super_env"


def test_environment_variable_local_and_local_are_distinct_names(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base = _write_base(tmp_path, environment="local")
    monkeypatch.setenv("ENVIRONMENT", "LOCAL")

    assert resolve_active_environment(base) == "LOCAL"
