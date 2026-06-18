"""Unit tests for appsettings file discovery."""

from pathlib import Path

import pytest

from pepelats.configuration.appsettings_discovery import (
    collect_appsettings_files,
    require_base_appsettings_file,
)
from pepelats.configuration.errors import ConfigurationError


def test_require_base_prefers_toml_over_json(tmp_path: Path) -> None:
    (tmp_path / "appsettings.toml").write_text("", encoding="utf-8")
    (tmp_path / "appsettings.json").write_text("{}", encoding="utf-8")

    assert require_base_appsettings_file(tmp_path) == tmp_path / "appsettings.toml"


def test_require_base_accepts_json_when_toml_is_missing(tmp_path: Path) -> None:
    (tmp_path / "appsettings.json").write_text("{}", encoding="utf-8")

    assert require_base_appsettings_file(tmp_path) == tmp_path / "appsettings.json"


def test_require_base_raises_when_no_supported_file_exists(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError, match="No base appsettings file"):
        require_base_appsettings_file(tmp_path)


def test_environment_overlay_is_optional(tmp_path: Path) -> None:
    (tmp_path / "appsettings.toml").write_text("", encoding="utf-8")
    (tmp_path / "appsettings.Staging.toml").write_text("", encoding="utf-8")

    assert collect_appsettings_files(tmp_path, "Production") == [
        tmp_path / "appsettings.toml",
    ]


def test_collect_merges_base_with_environment_overlay(tmp_path: Path) -> None:
    (tmp_path / "appsettings.toml").write_text("", encoding="utf-8")
    (tmp_path / "appsettings.local.toml").write_text("", encoding="utf-8")

    assert collect_appsettings_files(tmp_path, "local") == [
        tmp_path / "appsettings.toml",
        tmp_path / "appsettings.local.toml",
    ]


def test_collect_is_base_only_when_environment_overlay_is_missing(tmp_path: Path) -> None:
    (tmp_path / "appsettings.json").write_text("{}", encoding="utf-8")

    assert collect_appsettings_files(tmp_path, "Production") == [
        tmp_path / "appsettings.json",
    ]


def test_collect_finds_overlay_files_case_insensitively(tmp_path: Path) -> None:
    base = tmp_path / "appsettings.toml"
    overlay = tmp_path / "appsettings.my_suPeR_enV.json"
    base.write_text("", encoding="utf-8")
    overlay.write_text("{}", encoding="utf-8")

    assert collect_appsettings_files(tmp_path, "my_super_env", base_file=base) == [
        base,
        overlay,
    ]


def test_rejects_ambiguous_casing_for_same_stem(tmp_path: Path) -> None:
    (tmp_path / "appsettings.toml").write_text("", encoding="utf-8")
    (tmp_path / "appsettings.local.toml").write_text("", encoding="utf-8")
    (tmp_path / "appsettings.Local.json").write_text("{}", encoding="utf-8")

    with pytest.raises(ConfigurationError, match="Ambiguous appsettings files"):
        collect_appsettings_files(tmp_path, "local")
