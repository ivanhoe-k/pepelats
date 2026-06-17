"""Callback type for layer extensions (add_application, add_infrastructure)."""

from collections.abc import Callable

from pepelats.configuration import Configuration
from pepelats.dependency_injection import ServiceCollection

ServiceConfigurator = Callable[[ServiceCollection, Configuration], None]
