"""Unit tests for DynaconfConfiguration over a settings double."""

import pytest
from doubles import FakeSettings
from pydantic import BaseModel, ValidationError

from pepelats.configuration import ConfigurationError
from pepelats.configuration.configuration import DynaconfConfiguration
from pepelats.hosting.server_config import ServerConfig
from pepelats.observability.logging_config import LoggingConfig


class DatabaseConfig(BaseModel):
    url: str


class AzureBusConfig(BaseModel):
    connection_string: str


class Cache(BaseModel):
    ttl_seconds: int


class _ToDict:
    """Mimics a Dynaconf section exposing ``to_dict`` rather than a plain dict."""

    def __init__(self, data: dict[str, object]) -> None:
        self._data = data

    def to_dict(self) -> dict[str, object]:
        return dict(self._data)


@pytest.mark.parametrize(
    ("model", "section"),
    [
        (DatabaseConfig, "database"),
        (AzureBusConfig, "azure_bus"),
        (Cache, "cache"),
    ],
)
def test_get_derives_section_name_from_model(
    model: type[BaseModel], section: str
) -> None:
    payload: dict[str, object] = (
        {"ttl_seconds": 30}
        if model is Cache
        else {"url": "x", "connection_string": "x"}
    )
    configuration = DynaconfConfiguration(FakeSettings({section: payload}))

    result = configuration.get(model)

    assert isinstance(result, model)


def test_get_uses_explicit_section_over_derived_name() -> None:
    configuration = DynaconfConfiguration(
        FakeSettings({"primary_db": {"url": "postgres://"}})
    )

    result = configuration.get(DatabaseConfig, section="primary_db")

    assert result.url == "postgres://"


def test_try_get_returns_none_for_missing_section() -> None:
    configuration = DynaconfConfiguration(FakeSettings())

    assert configuration.try_get(DatabaseConfig) is None


def test_get_raises_for_missing_section() -> None:
    configuration = DynaconfConfiguration(FakeSettings())

    with pytest.raises(ConfigurationError):
        configuration.get(DatabaseConfig)


def test_get_validates_on_read() -> None:
    configuration = DynaconfConfiguration(
        FakeSettings({"cache": {"ttl_seconds": "nope"}})
    )

    with pytest.raises(ValidationError):
        configuration.get(Cache)


def test_get_value_returns_configured_value_as_str() -> None:
    configuration = DynaconfConfiguration(FakeSettings({"workers": 5}))

    assert configuration.get_value("workers") == "5"


def test_get_value_falls_back_to_default() -> None:
    configuration = DynaconfConfiguration(FakeSettings())

    assert configuration.get_value("missing", default="fallback") == "fallback"


def test_get_value_raises_when_missing_and_no_default() -> None:
    configuration = DynaconfConfiguration(FakeSettings())

    with pytest.raises(ConfigurationError):
        configuration.get_value("missing")


def test_get_section_dict_coerces_to_dict() -> None:
    configuration = DynaconfConfiguration(
        FakeSettings({"service": _ToDict({"name": "test-service"})})
    )

    assert configuration.get_section_dict("service") == {"name": "test-service"}


def test_get_preserves_dict_data_keys_while_binding_structural_fields() -> None:
    configuration = DynaconfConfiguration(
        FakeSettings(
            {
                "logging": {
                    "log_level": "INFO",
                    "overrides": {
                        "MyApp.Worker": "DEBUG",
                        "Uvicorn.Access": "ERROR",
                    },
                }
            }
        )
    )

    logging = configuration.get(LoggingConfig, section="logging")

    assert logging.overrides == {
        "MyApp.Worker": "DEBUG",
        "Uvicorn.Access": "ERROR",
    }


def test_get_section_dict_preserves_dict_data_keys() -> None:
    configuration = DynaconfConfiguration(
        FakeSettings(
            {
                "logging": {
                    "overrides": {
                        "MyApp.Worker": "DEBUG",
                        "Uvicorn.Access": "ERROR",
                    }
                }
            }
        )
    )

    section = configuration.get_section_dict("logging")

    assert section["overrides"] == {
        "MyApp.Worker": "DEBUG",
        "Uvicorn.Access": "ERROR",
    }


def test_get_binds_dynaconf_uppercase_structural_field_names() -> None:
    configuration = DynaconfConfiguration(
        FakeSettings({"host": {"PORT": 9001, "bind": "127.0.0.1"}})
    )

    server = configuration.get(ServerConfig, section="host")

    assert server.port == 9001
    assert server.bind == "127.0.0.1"


def test_get_section_dict_raises_for_missing_section() -> None:
    configuration = DynaconfConfiguration(FakeSettings())

    with pytest.raises(ConfigurationError):
        configuration.get_section_dict("service")


def test_get_section_dict_raises_for_non_section_value() -> None:
    configuration = DynaconfConfiguration(FakeSettings({"service": "not-a-section"}))

    with pytest.raises(ConfigurationError):
        configuration.get_section_dict("service")
