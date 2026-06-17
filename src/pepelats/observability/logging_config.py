"""Typed [logging] section: level, sinks, console/file options."""

from __future__ import annotations

import logging
from typing import Self

from pydantic import BaseModel, Field, field_validator, model_validator

_LOG_LEVEL_NAMES = frozenset(
    name
    for name in dir(logging)
    if name.isupper() and isinstance(getattr(logging, name), int)
)


class ConsoleSinkConfig(BaseModel):
    json_logs: bool = Field(default=False)


class FileSinkConfig(BaseModel):
    dir: str = Field(default="logs")
    file_name: str = Field(default="app.log")


class LoggingConfig(BaseModel):
    log_level: str = Field(default="INFO")
    sinks: list[str] = Field(default_factory=lambda: ["console", "file"])
    console: ConsoleSinkConfig = Field(default_factory=ConsoleSinkConfig)
    file: FileSinkConfig = Field(default_factory=FileSinkConfig)
    overrides: dict[str, str] = Field(default_factory=dict)

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        level_name = value.upper()
        if level_name not in _LOG_LEVEL_NAMES:
            msg = f"unknown log level: {value!r}"
            raise ValueError(msg)
        return level_name

    @model_validator(mode="after")
    def validate_overrides(self) -> Self:
        for logger_name, level_name in self.overrides.items():
            if level_name.upper() not in _LOG_LEVEL_NAMES:
                msg = (
                    f"unknown log level {level_name!r} "
                    f"for logger override {logger_name!r}"
                )
                raise ValueError(msg)
        return self
