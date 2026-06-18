"""Map raw section data onto Pydantic model fields before validation.

Dynaconf may upper-case keys (especially from env vars). Model fields are
case-insensitive at bind time. Keys inside dict-valued fields (e.g. logger names
in logging.overrides) are data, not schema, and are left unchanged.
"""

from __future__ import annotations

import types
from typing import Annotated, Any, Union, get_args, get_origin

from pydantic import BaseModel


def validate_section[TModel: BaseModel](
    model: type[TModel],
    data: Any,
) -> TModel:
    """Bind a section dict to a model with schema-aware key matching."""
    return model.model_validate(coerce_section_data_for_model(data, model))


def read_section_field[T](
    data: dict[str, Any],
    model: type[BaseModel],
    field_name: str,
    *,
    default: T,
) -> T:
    """Read one model field from a flat section dict with case-insensitive keys."""
    field_info = model.model_fields.get(field_name)
    if field_info is None:
        return default

    for key, value in data.items():
        if isinstance(key, str) and key.lower() == field_name.lower():
            coerced = _coerce_field_value(value, field_info.annotation)
            validated = model.model_validate({field_name: coerced})
            return getattr(validated, field_name)

    return default


def coerce_section_data_for_model(
    data: Any,
    model: type[BaseModel],
) -> Any:
    if not isinstance(data, dict):
        return data

    field_lookup = {name.lower(): name for name in model.model_fields}
    coerced: dict[str, Any] = {}

    for key, value in data.items():
        if not isinstance(key, str):
            coerced[key] = value
            continue

        field_name = field_lookup.get(key.lower())
        if field_name is None:
            coerced[key] = value
            continue

        field_info = model.model_fields[field_name]
        coerced[field_name] = _coerce_field_value(value, field_info.annotation)

    return coerced


def _coerce_field_value(value: Any, annotation: Any) -> Any:
    nested_model = _unwrap_base_model_type(annotation)
    if nested_model is not None and isinstance(value, dict):
        return coerce_section_data_for_model(value, nested_model)

    list_item_model = _unwrap_list_item_model_type(annotation)
    if list_item_model is not None:
        list_value = _indexed_dict_to_list(value)
        if isinstance(list_value, list):
            return [
                coerce_section_data_for_model(item, list_item_model)
                if isinstance(item, dict)
                else item
                for item in list_value
            ]

    dict_value_model = _unwrap_dict_value_model_type(annotation)
    if dict_value_model is not None and isinstance(value, dict):
        return {
            key: (
                coerce_section_data_for_model(item, dict_value_model)
                if isinstance(item, dict)
                else item
            )
            for key, item in value.items()
        }

    return value


def _indexed_dict_to_list(value: Any) -> Any:
    if not isinstance(value, dict) or not value:
        return value

    if not all(_is_index_key(key) for key in value):
        return value

    ordered_keys = sorted(value.keys(), key=lambda key: int(str(key)))
    return [value[key] for key in ordered_keys]


def _is_index_key(key: Any) -> bool:
    return isinstance(key, (str, int)) and str(key).isdigit()


def _unwrap_base_model_type(annotation: Any) -> type[BaseModel] | None:
    annotation = _unwrap_optional(annotation)
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return annotation
    return None


def _unwrap_list_item_model_type(annotation: Any) -> type[BaseModel] | None:
    annotation = _unwrap_optional(annotation)
    if get_origin(annotation) is list:
        args = get_args(annotation)
        if len(args) == 1:
            return _unwrap_base_model_type(args[0])
    return None


def _unwrap_dict_value_model_type(annotation: Any) -> type[BaseModel] | None:
    annotation = _unwrap_optional(annotation)
    if get_origin(annotation) is dict:
        args = get_args(annotation)
        if len(args) == 2:
            return _unwrap_base_model_type(args[1])
    return None


def _unwrap_optional(annotation: Any) -> Any:
    origin = get_origin(annotation)
    if origin is Annotated:
        return _unwrap_optional(get_args(annotation)[0])

    if origin is Union or origin is types.UnionType:
        args = [arg for arg in get_args(annotation) if arg is not type(None)]
        if len(args) == 1:
            return _unwrap_optional(args[0])

    return annotation
