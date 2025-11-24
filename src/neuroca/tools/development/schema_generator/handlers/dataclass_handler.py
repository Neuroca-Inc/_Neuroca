"""Source handler for Python dataclasses."""

from __future__ import annotations

import importlib
import inspect
import logging
from dataclasses import MISSING, fields, is_dataclass
from typing import Any, Optional, Sequence, Type

from ..exceptions.invalid_source_error import InvalidSourceError
from ..exceptions.schema_generation_error import SchemaGenerationError
from ..utilities.schema_utils import python_type_to_json_schema
from .base import SourceHandler

LOGGER = logging.getLogger(__name__)


class DataclassSourceHandler(SourceHandler):
    """Generate schema data from dataclass definitions."""

    def generate(self, source: Any, namespace: Optional[str] = None) -> dict[str, Any]:
        """Produce schema data for dataclass sources."""
        try:
            resolved = self._resolve_source(source)
            if inspect.ismodule(resolved):
                dataclasses = self._collect_dataclasses(resolved)
                if not dataclasses:
                    raise InvalidSourceError(f"No dataclasses found in module: {resolved.__name__}")
                return self._build_module_schema(dataclasses, namespace or resolved.__name__)
            if inspect.isclass(resolved) and is_dataclass(resolved):
                return self._build_single_schema(resolved, namespace)
            raise InvalidSourceError(
                "Source must be a dataclass, a module containing dataclasses, or a path to such a module",
            )
        except SchemaGenerationError:
            raise
        except Exception as exc:  # noqa: BLE001
            LOGGER.error("Error generating schema from dataclass source: %s", exc, exc_info=True)
            raise SchemaGenerationError(f"Dataclass schema generation failed: {exc}") from exc

    @staticmethod
    def _resolve_source(source: Any) -> Any:
        """Resolve string references into importable modules."""
        if isinstance(source, str):
            try:
                return importlib.import_module(source)
            except ImportError as exc:
                raise InvalidSourceError(f"Could not import module: {source}") from exc
        return source

    @staticmethod
    def _collect_dataclasses(module: Any) -> list[Type[Any]]:
        """Collect dataclass definitions from a module."""
        return [
            obj
            for _, obj in inspect.getmembers(module)
            if inspect.isclass(obj) and is_dataclass(obj)
        ]

    def _build_module_schema(self, dataclasses: Sequence[Type[Any]], title: str) -> dict[str, Any]:
        """Assemble schema data for a module containing dataclasses."""
        schema_data: dict[str, Any] = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "title": title,
            "type": "object",
            "definitions": {},
        }
        for dataclass_obj in dataclasses:
            schema_data["definitions"][dataclass_obj.__name__] = self._build_properties(dataclass_obj)
        return schema_data

    def _build_single_schema(self, dataclass_obj: Type[Any], namespace: Optional[str]) -> dict[str, Any]:
        """Generate schema data for a single dataclass."""
        schema = self._build_properties(dataclass_obj)
        if namespace:
            schema["title"] = namespace
        return schema

    def _build_properties(self, dataclass_obj: Type[Any]) -> dict[str, Any]:
        """Build the JSON schema properties for a dataclass."""
        schema = {
            "type": "object",
            "title": dataclass_obj.__name__,
            "properties": {},
            "required": [],
        }
        for field in fields(dataclass_obj):
            schema["properties"][field.name] = python_type_to_json_schema(field.type)
            if field.default is MISSING and field.default_factory is MISSING:
                schema["required"].append(field.name)
        if not schema["required"]:
            schema.pop("required")
        return schema


__all__ = ["DataclassSourceHandler"]
