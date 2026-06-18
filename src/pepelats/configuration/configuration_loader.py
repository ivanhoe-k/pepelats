"""Load appsettings from disk into a ConfigurationBootstrap."""

from pathlib import Path

from pepelats.configuration.appsettings_discovery import (
    collect_appsettings_files,
    require_base_appsettings_file,
)
from pepelats.configuration.appsettings_environment import resolve_active_environment
from pepelats.configuration.configuration import DynaconfConfiguration
from pepelats.configuration.configuration_bootstrap import ConfigurationBootstrap
from pepelats.configuration.dynaconf_loader import get_dynaconf_settings
from pepelats.configuration.environment import Environment


def load_configuration(
    config_dir: Path,
    *,
    environment: str | None = None,
) -> ConfigurationBootstrap:
    base_file = require_base_appsettings_file(config_dir)
    active_environment = resolve_active_environment(base_file, override=environment)
    settings_files = collect_appsettings_files(
        config_dir,
        active_environment,
        base_file=base_file,
    )
    settings = get_dynaconf_settings(settings_files)
    return ConfigurationBootstrap(
        configuration=DynaconfConfiguration(settings),
        environment=Environment(name=active_environment),
    )
