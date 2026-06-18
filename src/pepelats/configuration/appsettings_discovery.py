"""Discover appsettings files on disk. No Dynaconf dependency."""

from __future__ import annotations

from pathlib import Path

from pepelats.configuration.errors import ConfigurationError

_CONFIG_EXTENSIONS = (".toml", ".json")
_BASE_STEM = "appsettings"


def require_base_appsettings_file(config_dir: Path) -> Path:
    available = _list_settings_files(config_dir)
    match = _resolve_unique_settings_file(available, _BASE_STEM)
    if match is None:
        msg = f"No base appsettings file found in {config_dir}"
        raise ConfigurationError(msg)
    return match


def collect_appsettings_files(
    config_dir: Path,
    environment: str,
    *,
    base_file: Path | None = None,
) -> list[Path]:
    available = _list_settings_files(config_dir)
    base = base_file or _resolve_unique_settings_file(available, _BASE_STEM)
    if base is None:
        msg = f"No base appsettings file found in {config_dir}"
        raise ConfigurationError(msg)

    files = [base]
    overlay = _resolve_unique_settings_file(available, f"appsettings.{environment}")
    if overlay is not None:
        files.append(overlay)
    return files


def _list_settings_files(config_dir: Path) -> list[Path]:
    if not config_dir.is_dir():
        return []
    return [
        path
        for path in config_dir.iterdir()
        if path.is_file() and path.suffix in _CONFIG_EXTENSIONS
    ]


def _resolve_unique_settings_file(
    available: list[Path],
    stem: str,
) -> Path | None:
    stem_lower = stem.lower()
    matches = [path for path in available if path.stem.lower() == stem_lower]
    if not matches:
        return None

    distinct_stems = {path.stem for path in matches}
    if len(distinct_stems) > 1:
        names = ", ".join(sorted(path.name for path in matches))
        msg = f"Ambiguous appsettings files for {stem}: {names}"
        raise ConfigurationError(msg)

    for extension in _CONFIG_EXTENSIONS:
        for path in matches:
            if path.suffix == extension:
                return path

    return None
