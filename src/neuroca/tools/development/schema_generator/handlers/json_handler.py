"""Source handler for JSON and dictionary inputs."""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional

from ..exceptions.invalid_source_error import InvalidSourceError
from ..exceptions.schema_generation_error import SchemaGenerationError
from ..utilities.schema_utils import infer_type
from .base import SourceHandler

LOGGER = logging.getLogger(__name__)


class JsonSourceHandler(SourceHandler):
    """Generate schema data from JSON structures."""

    def generate(self, source: Any, namespace: Optional[str] = None) -> dict[str, Any]:
        """Produce schema data for JSON strings, files, or dictionaries."""
        try:
            data = self._load_source(source)
            return self._build_schema(data, namespace)
        except SchemaGenerationError:
            raise
        except Exception as exc:  # noqa: BLE001
            LOGGER.error("Error generating schema from JSON source: %s", exc, exc_info=True)
            raise SchemaGenerationError(f"JSON schema generation failed: {exc}") from exc

    def _load_source(self, source: Any) -> Any:
        """Load and return structured data from the provided source."""
        if isinstance(source, (dict, list)):
            return source
        if isinstance(source, str) and self._looks_like_path(source):
            try:
                with open(source) as handle:
                    return json.load(handle)
            except Exception as exc:  # noqa: BLE001
                raise InvalidSourceError(f"Failed to load JSON from file {source}: {exc}") from exc
        if isinstance(source, str):
            try:
                return json.loads(source)
            except json.JSONDecodeError as exc:
                raise InvalidSourceError("Invalid JSON string") from exc
        raise InvalidSourceError("Source must be a JSON string, file path, or parsed JSON object")

    @staticmethod
    def _looks_like_path(value: str) -> bool:
        """Return True if the string resembles a filesystem path."""
        return os.path.exists(value) or value.startswith("./") or value.startswith("/")

    def _build_schema(self, data: Any, namespace: Optional[str]) -> dict[str, Any]:
        """Build JSON schema data from arbitrary structured input."""
        schema_data: dict[str, Any] = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "title": namespace or "JSON Schema",
        }
        if isinstance(data, dict):
            schema_data["type"] = "object"
            schema_data["properties"] = {key: infer_type(value) for key, value in data.items()}
        elif isinstance(data, list):
            schema_data["type"] = "array"
            schema_data["items"] = infer_type(data[0]) if data else {}
        else:
            schema_data.update(infer_type(data))
        return schema_data


__all__ = ["JsonSourceHandler"]
