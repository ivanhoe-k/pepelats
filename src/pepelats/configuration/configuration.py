"""Configuration reader — business layers read config without knowing Dynaconf.

A typed, source-agnostic view over loaded settings.
"""

from abc import ABC, abstractmethod
from typing import Any, cast

from pydantic import BaseModel

from pepelats.configuration.errors import ConfigurationError
from pepelats.configuration.section_coercion import validate_section
from pepelats.configuration.section_names import default_section_name


class Configuration(ABC):
    """Typed, source-agnostic configuration reader."""

    @abstractmethod
    def get_value(self, key: str, default: str | None = None) -> str: ...

    @abstractmethod
    def get_section_dict(self, section: str) -> dict[str, Any]: ...

    @abstractmethod
    def get[TConfig: BaseModel](
        self,
        model: type[TConfig],
        *,
        section: str | None = None,
    ) -> TConfig: ...

    @abstractmethod
    def try_get[TConfig: BaseModel](
        self,
        model: type[TConfig],
        *,
        section: str | None = None,
    ) -> TConfig | None: ...


class DynaconfConfiguration(Configuration):
    def __init__(self, inner: Any) -> None:
        self._inner = inner

    def get_value(self, key: str, default: str | None = None) -> str:
        value = self._inner.get(key, default)
        if value is None:
            if default is None:
                msg = f"{key} is not configured"
                raise ConfigurationError(msg)
            return default
        return str(value)

    def get[TConfig: BaseModel](
        self,
        model: type[TConfig],
        *,
        section: str | None = None,
    ) -> TConfig:
        configuration = self.try_get(model, section=section)
        if configuration is None:
            section_name = section or default_section_name(model)
            msg = f"{section_name} is not configured"
            raise ConfigurationError(msg)
        return configuration

    def try_get[TConfig: BaseModel](
        self,
        model: type[TConfig],
        *,
        section: str | None = None,
    ) -> TConfig | None:
        section_name = section or default_section_name(model)
        section_data = self._read_section(section_name)
        if section_data is None:
            return None
        return validate_section(model, section_data)

    def get_section_dict(self, section: str) -> dict[str, Any]:
        section_data = self._read_section(section)
        if section_data is None:
            msg = f"{section} is not configured"
            raise ConfigurationError(msg)
        return section_data

    def _read_section(self, section: str) -> dict[str, Any] | None:
        value = self._inner.get(section)
        if value is None:
            return None

        if hasattr(value, "to_dict"):
            return cast(dict[str, Any], value.to_dict())

        if isinstance(value, dict):
            return value

        msg = f"{section} is not a configuration section"
        raise ConfigurationError(msg)
