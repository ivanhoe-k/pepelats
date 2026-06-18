"""Read the environment name from the base appsettings file only."""

from __future__ import annotations

import json
import tomllib
from pathlib import Path
from typing import Any

from pepelats.configuration.errors import ConfigurationError

_ENVIRONMENT_KEY = "environment"


def read_environment_from_base(
    base_file: Path,
    *,
    default: str,
) -> str:
    document = _load_document(base_file)
    value = document.get(_ENVIRONMENT_KEY)
    if value is None:
        return default
    if not isinstance(value, str) or not value.strip():
        msg = f"{_ENVIRONMENT_KEY} in {base_file} must be a non-empty string"
        raise ConfigurationError(msg)
    return value


def _load_document(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as error:
        msg = f"Failed to read {path}"
        raise ConfigurationError(msg) from error

    try:
        loaded = json.loads(raw) if path.suffix == ".json" else tomllib.loads(raw)
    except (json.JSONDecodeError, tomllib.TOMLDecodeError) as error:
        msg = f"Failed to parse {path}"
        raise ConfigurationError(msg) from error

    if not isinstance(loaded, dict):
        msg = f"{path} must contain a top-level mapping"
        raise ConfigurationError(msg)
    return loaded
