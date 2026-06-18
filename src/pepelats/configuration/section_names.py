"""Derive appsettings section names from configuration model types."""

from pydantic import BaseModel


def default_section_name(model: type[BaseModel]) -> str:
    name = model.__name__
    if name.endswith("Config"):
        name = name[: -len("Config")]
    return _pascal_to_snake(name)


def _pascal_to_snake(value: str) -> str:
    chars: list[str] = []
    for index, char in enumerate(value):
        if char.isupper() and index > 0:
            chars.append("_")
        chars.append(char.lower())
    return "".join(chars)
