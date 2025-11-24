"""Source handler for plain Python classes."""

from __future__ import annotations

import importlib
import inspect
import logging
from typing import Any, Optional, Sequence, Type

from ..exceptions.invalid_source_error import InvalidSourceError
from ..exceptions.schema_generation_error import SchemaGenerationError
from ..utilities.schema_utils import python_type_to_json_schema
from .base import SourceHandler

LOGGER = logging.getLogger(__name__)


class ClassSourceHandler(SourceHandler):
    """Generate schema data from Python class definitions."""

    def generate(self, source: Any, namespace: Optional[str] = None) -> dict[str, Any]:
        """Produce schema data for classes or modules of classes."""
        try:
            resolved = self._resolve_source(source)
            if inspect.ismodule(resolved):
                classes = self._collect_classes(resolved)
                if not classes:
                    raise InvalidSourceError(f"No classes found in module: {resolved.__name__}")
                return self._build_module_schema(classes, namespace or resolved.__name__)
            if inspect.isclass(resolved):
                return self._build_class_schema(resolved, namespace)
            raise InvalidSourceError(
                "Source must be a class, a module containing classes, or a path to such a module",
            )
        except SchemaGenerationError:
            raise
        except Exception as exc:  # noqa: BLE001
            LOGGER.error("Error generating schema from class source: %s", exc, exc_info=True)
            raise SchemaGenerationError(f"Class schema generation failed: {exc}") from exc

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
    def _collect_classes(module: Any) -> list[Type[Any]]:
        """Collect classes defined directly in the given module."""
        return [
            obj
            for _, obj in inspect.getmembers(module)
            if inspect.isclass(obj) and obj.__module__ == module.__name__
        ]

    def _build_module_schema(self, classes: Sequence[Type[Any]], title: str) -> dict[str, Any]:
        """Assemble schema data for a module containing class definitions."""
        schema_data: dict[str, Any] = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "title": title,
            "type": "object",
            "definitions": {},
        }
        for cls in classes:
            schema_data["definitions"][cls.__name__] = self._class_properties(cls)
        return schema_data

    def _build_class_schema(self, cls: Type[Any], namespace: Optional[str]) -> dict[str, Any]:
        """Generate schema data for a single class."""
        schema = self._class_properties(cls)
        if namespace:
            schema["title"] = namespace
        return schema

    def _class_properties(self, cls: Type[Any]) -> dict[str, Any]:
        """Build the schema properties for a Python class."""
        schema = {
            "type": "object",
            "title": cls.__name__,
            "properties": {},
        }
        for name, annotation in getattr(cls, "__annotations__", {}).items():
            schema["properties"][name] = python_type_to_json_schema(annotation)
        if hasattr(cls, "__init__"):
            signature = inspect.signature(cls.__init__)
            for param_name, param in signature.parameters.items():
                if param_name == "self" or param_name in schema["properties"]:
                    continue
                if param.annotation is not inspect.Parameter.empty:
                    schema["properties"][param_name] = python_type_to_json_schema(param.annotation)
                else:
                    schema["properties"][param_name] = {"type": "string"}
        return schema


__all__ = ["ClassSourceHandler"]
