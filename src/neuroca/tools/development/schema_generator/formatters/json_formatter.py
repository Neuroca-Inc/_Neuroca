"""Formatter implementation for JSON schema output."""

from __future__ import annotations

import json
import logging
from typing import Any

from ..exceptions.schema_generation_error import SchemaGenerationError
from .base import SchemaFormatter

LOGGER = logging.getLogger(__name__)


class JsonSchemaFormatter(SchemaFormatter):
    """Render schema dictionaries as JSON strings."""

    def format(self, schema_data: dict[str, Any]) -> str:
        """Serialize the schema data to JSON."""
        try:
            return json.dumps(schema_data, indent=2)
        except Exception as exc:  # noqa: BLE001
            LOGGER.error("Failed to format JSON schema: %s", exc)
            raise SchemaGenerationError(f"JSON formatting error: {exc}") from exc

    def get_file_extension(self) -> str:
        """Return the default JSON file extension."""
        return ".json"


__all__ = ["JsonSchemaFormatter"]
