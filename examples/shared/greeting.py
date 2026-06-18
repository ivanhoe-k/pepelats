"""Shared services and config for the HTTP greeting examples."""

from abc import ABC, abstractmethod

from pydantic import BaseModel

from pepelats.configuration import Configuration
from pepelats.dependency_injection import ServiceCollection


class Greeter(ABC):
    @abstractmethod
    def greet(self, name: str) -> str: ...


class FriendlyGreeter(Greeter):
    def greet(self, name: str) -> str:
        return f"Hello, {name}"


class RequestCounter:
    def __init__(self) -> None:
        self._count = 0

    def increment(self) -> int:
        self._count += 1
        return self._count


class GreetingConfig(BaseModel):
    punctuation: str
    shout: bool


class User(BaseModel):
    id: int
    name: str


class Repository[TEntity, TKey]:
    def __init__(self) -> None:
        self._items: dict[object, object] = {}

    def count(self) -> int:
        return len(self._items)


def register(services: ServiceCollection, configuration: Configuration) -> None:
    services.add_scoped(Greeter, FriendlyGreeter)  # type: ignore[type-abstract]
    services.add_singleton(RequestCounter)
    services.add_configuration(GreetingConfig)
    services.add_scoped(Repository)
