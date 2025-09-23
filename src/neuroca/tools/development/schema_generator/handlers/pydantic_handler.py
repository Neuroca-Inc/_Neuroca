"""Source handler for generating schemas from Pydantic models."""

from __future__ import annotations

import importlib
import inspect
import logging
from types import ModuleType
from typing import Any, Iterable, Optional, Type

from ..exceptions.invalid_source_error import InvalidSourceError
from ..exceptions.schema_generation_error import SchemaGenerationError
from .base import SourceHandler

LOGGER = logging.getLogger(__name__)


class PydanticSourceHandler(SourceHandler):
    """Generate schema data from Pydantic model definitions."""

    def generate(self, source: Any, namespace: Optional[str] = None) -> dict[str, Any]:
        """Produce schema data for Pydantic sources."""
        try:
            base_model = self._import_base_model()
            resolved_source = self._resolve_source(source)
            if inspect.ismodule(resolved_source):
                models = self._collect_models(resolved_source, base_model)
                if not models:
                    raise InvalidSourceError(
                        f"No Pydantic models found in module: {resolved_source.__name__}",
                    )
                return self._build_module_schema(models, namespace or resolved_source.__name__)
            if inspect.isclass(resolved_source) and issubclass(resolved_source, base_model):
                return self._build_model_schema(resolved_source, namespace)
            raise InvalidSourceError(
                "Source must be a Pydantic model, a module containing Pydantic models, or a path to such a module",
            )
        except SchemaGenerationError:
            raise
        except Exception as exc:  # noqa: BLE001
            LOGGER.error("Error generating schema from Pydantic source: %s", exc, exc_info=True)
            raise SchemaGenerationError(f"Pydantic schema generation failed: {exc}") from exc

    @staticmethod
    def _import_base_model() -> Type[Any]:
        """Import and return the Pydantic BaseModel class."""
        try:
            from pydantic import BaseModel  # type: ignore import-not-found

            return BaseModel
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise SchemaGenerationError("Pydantic package is required for Pydantic schema generation") from exc

    @staticmethod
    def _resolve_source(source: Any) -> Any:
        """Resolve string references to modules and return the concrete object."""
        if isinstance(source, str):
            try:
                return importlib.import_module(source)
            except ImportError as exc:
                raise InvalidSourceError(f"Could not import module: {source}") from exc
        return source

    @staticmethod
    def _collect_models(module: ModuleType, base_model: Type[Any]) -> list[Type[Any]]:
        """Collect BaseModel subclasses defined in the provided module."""
        return [
            obj
            for _, obj in inspect.getmembers(module)
            if inspect.isclass(obj) and issubclass(obj, base_model) and obj is not base_model
        ]

    @staticmethod
    def _build_module_schema(models: Iterable[Type[Any]], title: str) -> dict[str, Any]:
        """Assemble schema data for a module containing multiple Pydantic models."""
        schema_data: dict[str, Any] = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "title": title,
            "type": "object",
            "definitions": {},
        }
        for model in models:
            schema_data["definitions"][model.__name__] = model.schema()
        return schema_data

    def _build_model_schema(self, model: Type[Any], namespace: Optional[str]) -> dict[str, Any]:
        """Generate schema data for a single Pydantic model."""
        schema = model.schema()
        if namespace:
            schema["title"] = namespace
        return schema


__all__ = ["PydanticSourceHandler"]
