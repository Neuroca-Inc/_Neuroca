"""Formatter implementation for YAML schema output."""

from __future__ import annotations

import logging
from typing import Any

from ..exceptions.schema_generation_error import SchemaGenerationError
from .base import SchemaFormatter

LOGGER = logging.getLogger(__name__)


class YamlSchemaFormatter(SchemaFormatter):
    """Render schema dictionaries as YAML strings."""

    def format(self, schema_data: dict[str, Any]) -> str:
        """Serialize the schema data to YAML."""
        try:
            import yaml

            return yaml.dump(schema_data, default_flow_style=False)
        except ImportError as exc:
            LOGGER.error("PyYAML package is required for YAML formatting")
            msg = "PyYAML package is required for YAML formatting"
            raise SchemaGenerationError(msg) from exc
        except Exception as exc:  # noqa: BLE001
            LOGGER.error("Failed to format YAML schema: %s", exc)
            raise SchemaGenerationError(f"YAML formatting error: {exc}") from exc

    def get_file_extension(self) -> str:
        """Return the default YAML file extension."""
        return ".yaml"


__all__ = ["YamlSchemaFormatter"]
