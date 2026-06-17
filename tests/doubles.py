"""Reusable test doubles for the pepelats suite (importable across test modules)."""

from typing import Any

from pepelats.dependency_injection.async_disposable import AsyncDisposable


class FakeSettings:
    """Dynaconf-settings stand-in: attribute and ``.get`` access over a dict."""

    def __init__(self, data: dict[str, Any] | None = None) -> None:
        self._data = data or {}

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def __getattr__(self, name: str) -> Any:
        try:
            return self._data[name]
        except KeyError as error:
            raise AttributeError(name) from error


class RecordingDisposable(AsyncDisposable):
    """Flags whether the container disposed it at the scope boundary."""

    def __init__(self) -> None:
        self.disposed = False

    async def dispose(self) -> None:
        self.disposed = True
