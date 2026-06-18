"""Only module that imports Dynaconf."""

from pathlib import Path

from dynaconf import Dynaconf
from dynaconf.loaders import env_loader, json_loader, toml_loader

_FILE_LOADERS = {
    ".toml": toml_loader.load,
    ".json": json_loader.load,
}


def get_dynaconf_settings(settings_files: list[Path]) -> Dynaconf:
    settings = Dynaconf(
        environments=False,
        merge_enabled=True,
        load_dotenv=True,
        envvar_prefix=False,
    )
    for path in settings_files:
        loader = _FILE_LOADERS[path.suffix]
        loader(settings, filename=str(path), env=False)
    env_loader.load(settings, env=False, silent=True)
    return settings
