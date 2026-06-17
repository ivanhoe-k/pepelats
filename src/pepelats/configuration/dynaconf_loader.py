"""Only module that imports Dynaconf. Loads TOML and env overrides."""

from pathlib import Path

from dynaconf import Dynaconf


def get_dynaconf_settings(config_dir: Path) -> Dynaconf:
    return Dynaconf(
        environments=True,
        settings_files=[
            str(config_dir / "appsettings.toml"),
            str(config_dir / "appsettings.local.toml"),
        ],
        env_switcher="ENVIRONMENT",
        load_dotenv=True,
        merge_enabled=True,
        envvar_prefix=False,
    )
