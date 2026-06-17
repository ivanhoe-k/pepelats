"""Vendor-neutral injection marker for request-scoped resolution.

`Inject[T]` marks a parameter that a transport integration should resolve from the
request-scoped `ServiceProvider`, rather than have the web framework parse it. It is
metadata only: at runtime `Inject[T]` is `Annotated[T, marker]`, so the parameter still
reads as `T` to type checkers and to any caller that ignores the marker.

The DI engine is hidden behind `ServiceProvider`; this marker keeps the app-facing
injection surface independent of it too.
"""

from typing import TYPE_CHECKING, Annotated, Any, TypeVar, get_args, get_origin

_T = TypeVar("_T")


class _InjectMarker:
    """Sentinel attached via `Annotated` to flag a request-scoped dependency."""

    __slots__ = ()


_MARKER = _InjectMarker()


if TYPE_CHECKING:
    from typing import Union

    # `Inject[T]` reads as `T` for type checkers (`Union[T, T]` collapses to `T`).
    Inject = Union[_T, _T]  # noqa: UP007
else:

    class Inject:
        def __class_getitem__(cls, item: Any) -> Any:
            return Annotated[item, _MARKER]


def injected_type(hint: Any) -> Any:
    """Return `T` if `hint` is an `Inject[T]` annotation, else `None`."""
    if get_origin(hint) is not Annotated:
        return None
    type_arg, *metadata = get_args(hint)
    return type_arg if any(meta is _MARKER for meta in metadata) else None
