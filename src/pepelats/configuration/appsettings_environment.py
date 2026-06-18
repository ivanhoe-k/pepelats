"""Resolve the active host environment name for appsettings overlay selection."""

from __future__ import annotations

import os
from pathlib import Path

from pepelats.configuration.appsettings_base_reader import read_environment_from_base
from pepelats.configuration.errors import ConfigurationError

DEFAULT_ENVIRONMENT_NAME = "Local"
_ENVIRONMENT_VARIABLE = "ENVIRONMENT"


def validate_environment_name(name: str) -> str:
    trimmed = name.strip()
    if not trimmed:
        msg = "Environment name must be a non-empty string"
        raise ConfigurationError(msg)
    return trimmed


def resolve_active_environment(
    base_file: Path,
    *,
    override: str | None = None,
) -> str:
    if override is not None:
        return validate_environment_name(override)

    from_environment = os.getenv(_ENVIRONMENT_VARIABLE)
    if from_environment:
        return validate_environment_name(from_environment)

    return validate_environment_name(
        read_environment_from_base(
            base_file,
            default=DEFAULT_ENVIRONMENT_NAME,
        )
    )
