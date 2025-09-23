"""Formatter implementation for Protocol Buffer schema output."""

from __future__ import annotations

import logging
from typing import Any

from ..exceptions.schema_generation_error import SchemaGenerationError
from .base import SchemaFormatter

LOGGER = logging.getLogger(__name__)


class ProtobufSchemaFormatter(SchemaFormatter):
    """Render schema dictionaries as simplified Protocol Buffer definitions."""

    def format(self, schema_data: dict[str, Any]) -> str:
        """Serialize the schema data to a Protocol Buffer definition string."""
        try:
            output = ["syntax = \"proto3\";\n"]
            package_name = schema_data.get("package", "neuroca")
            output.append(f"package {package_name};\n\n")
            for message_name, properties in schema_data.get("messages", {}).items():
                output.append(f"message {message_name} {{\n")
                for index, (prop_name, prop_details) in enumerate(properties.items(), start=1):
                    prop_type = prop_details.get("type", "string")
                    pb_type = self._map_type(prop_type)
                    output.append(f"  {pb_type} {prop_name} = {index};\n")
                output.append("}\n\n")
            return "".join(output)
        except Exception as exc:  # noqa: BLE001
            LOGGER.error("Failed to format Protobuf schema: %s", exc)
            raise SchemaGenerationError(f"Protobuf formatting error: {exc}") from exc

    def get_file_extension(self) -> str:
        """Return the default Protocol Buffer file extension."""
        return ".proto"

    @staticmethod
    def _map_type(prop_type: str) -> str:
        """Map schema property types to Protocol Buffer field types."""
        type_mapping = {
            "string": "string",
            "integer": "int32",
            "number": "float",
            "boolean": "bool",
            "object": "map<string, string>",
            "array": "repeated string",
        }
        return type_mapping.get(prop_type, "string")


__all__ = ["ProtobufSchemaFormatter"]
