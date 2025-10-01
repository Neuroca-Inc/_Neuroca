"""Source handler for SQLAlchemy models."""

from __future__ import annotations

import importlib
import inspect
import logging
from typing import Any, Optional, Sequence, Type

from ..exceptions.invalid_source_error import InvalidSourceError
from ..exceptions.schema_generation_error import SchemaGenerationError
from .base import SourceHandler

LOGGER = logging.getLogger(__name__)


class SqlAlchemySourceHandler(SourceHandler):
    """Generate schema data from SQLAlchemy declarative models."""

    def generate(self, source: Any, namespace: Optional[str] = None) -> dict[str, Any]:
        """Produce schema data for SQLAlchemy sources."""
        try:
            declarative_meta = self._import_declarative_meta()
            resolved = self._resolve_source(source)
            if inspect.ismodule(resolved):
                models = self._collect_models(resolved, declarative_meta)
                if not models:
                    raise InvalidSourceError(f"No SQLAlchemy models found in module: {resolved.__name__}")
                return self._build_module_schema(models, namespace or resolved.__name__)
            if inspect.isclass(resolved) and isinstance(resolved, declarative_meta):
                return self._build_single_schema(resolved, namespace)
            raise InvalidSourceError(
                "Source must be a SQLAlchemy model, a module containing SQLAlchemy models, or a path to such a module",
            )
        except SchemaGenerationError:
            raise
        except Exception as exc:  # noqa: BLE001
            LOGGER.error("Error generating schema from SQLAlchemy source: %s", exc, exc_info=True)
            raise SchemaGenerationError(f"SQLAlchemy schema generation failed: {exc}") from exc

    @staticmethod
    def _import_declarative_meta() -> Any:
        """Import the DeclarativeMeta class from SQLAlchemy."""
        try:
            from sqlalchemy.ext.declarative import DeclarativeMeta  # type: ignore import-not-found

            return DeclarativeMeta
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise SchemaGenerationError("SQLAlchemy package is required for SQLAlchemy schema generation") from exc

    @staticmethod
    def _resolve_source(source: Any) -> Any:
        """Resolve string references into modules."""
        if isinstance(source, str):
            try:
                return importlib.import_module(source)
            except ImportError as exc:
                raise InvalidSourceError(f"Could not import module: {source}") from exc
        return source

    @staticmethod
    def _collect_models(module: Any, declarative_meta: Any) -> list[Type[Any]]:
        """Collect SQLAlchemy model classes from a module."""
        return [
            obj
            for _, obj in inspect.getmembers(module)
            if inspect.isclass(obj) and isinstance(obj, declarative_meta)
        ]

    def _build_module_schema(self, models: Sequence[Type[Any]], title: str) -> dict[str, Any]:
        """Build schema data for a module of SQLAlchemy models."""
        schema_data: dict[str, Any] = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "title": title,
            "type": "object",
            "definitions": {},
        }
        for model in models:
            schema_data["definitions"][model.__name__] = self._model_to_schema(model)
        return schema_data

    def _build_single_schema(self, model: Type[Any], namespace: Optional[str]) -> dict[str, Any]:
        """Generate schema data for a single SQLAlchemy model."""
        schema = self._model_to_schema(model)
        if namespace:
            schema["title"] = namespace
        return schema

    def _model_to_schema(self, model: Type[Any]) -> dict[str, Any]:
        """Convert a SQLAlchemy model into a JSON schema fragment."""
        schema = {
            "type": "object",
            "title": model.__name__,
            "properties": {},
            "required": [],
        }
        for column_name, column in model.__table__.columns.items():  # type: ignore[attr-defined]
            column_schema = self._type_to_schema(column.type)
            if column.nullable is False:
                schema["required"].append(column_name)
            if hasattr(column.type, "length") and column.type.length is not None:
                column_schema["maxLength"] = column.type.length
            schema["properties"][column_name] = column_schema
        if not schema["required"]:
            schema.pop("required")
        return schema

    @staticmethod
    def _type_to_schema(sa_type: Any) -> dict[str, Any]:
        """Map SQLAlchemy column types to JSON schema fragments."""
        import sqlalchemy as sa  # type: ignore import-not-found

        if isinstance(sa_type, sa.String):
            return {"type": "string"}
        if isinstance(sa_type, sa.Integer):
            return {"type": "integer"}
        if isinstance(sa_type, sa.Float):
            return {"type": "number"}
        if isinstance(sa_type, sa.Boolean):
            return {"type": "boolean"}
        if isinstance(sa_type, sa.Date):
            return {"type": "string", "format": "date"}
        if isinstance(sa_type, sa.DateTime):
            return {"type": "string", "format": "date-time"}
        if isinstance(sa_type, sa.Enum):
            return {"type": "string", "enum": [enum_member for enum_member in sa_type.enums]}
        return {"type": "string"}


__all__ = ["SqlAlchemySourceHandler"]
