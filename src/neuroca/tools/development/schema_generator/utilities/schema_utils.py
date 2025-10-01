"""Shared helper functions for schema inference."""

from __future__ import annotations

from typing import Any, Union, get_args, get_origin


def python_type_to_json_schema(py_type: type) -> dict[str, Any]:
    """Convert a Python type annotation into a JSON schema fragment."""
    origin = get_origin(py_type)
    if py_type is str:
        return {"type": "string"}
    if py_type is int:
        return {"type": "integer"}
    if py_type is float:
        return {"type": "number"}
    if py_type is bool:
        return {"type": "boolean"}
    if py_type is list:
        return {"type": "array", "items": {}}
    if py_type is dict:
        return {"type": "object"}
    if origin is list:
        item_type = get_args(py_type)[0]
        return {"type": "array", "items": python_type_to_json_schema(item_type)}
    if origin is dict:
        return {"type": "object"}
    if origin is Union:
        items = [python_type_to_json_schema(arg) for arg in get_args(py_type) if arg is not type(None)]
        if len(items) == 1:
            return items[0]
        return {"anyOf": items}
    return {"type": "string"}


def infer_type(value: Any) -> dict[str, Any]:
    """Infer a JSON schema fragment from an arbitrary Python value."""
    if isinstance(value, dict):
        return {
            "type": "object",
            "properties": {key: infer_type(val) for key, val in value.items()},
        }
    if isinstance(value, list):
        if not value:
            return {"type": "array", "items": {}}
        return {"type": "array", "items": infer_type(value[0])}
    if isinstance(value, bool):
        return {"type": "boolean"}
    if isinstance(value, int):
        return {"type": "integer"}
    if isinstance(value, float):
        return {"type": "number"}
    return {"type": "string"}


__all__ = ["python_type_to_json_schema", "infer_type"]
