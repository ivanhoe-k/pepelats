"""Result of loading configuration from disk."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from pepelats.configuration.environment import Environment

if TYPE_CHECKING:
    from pepelats.configuration.configuration import Configuration


@dataclass(frozen=True, slots=True)
class ConfigurationBootstrap:
    configuration: Configuration
    environment: Environment
