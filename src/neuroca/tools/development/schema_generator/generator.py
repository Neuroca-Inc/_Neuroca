"""Main coordination class for schema generation."""

from __future__ import annotations

import datetime
import logging
from pathlib import Path
from typing import Any, Optional, Union

from .enums.schema_format import SchemaFormat
from .enums.source_type import SourceType
from .exceptions.invalid_source_error import InvalidSourceError
from .exceptions.schema_generation_error import SchemaGenerationError
from .exceptions.unsupported_format_error import UnsupportedFormatError
from .formatters import (
    JsonSchemaFormatter,
    ProtobufSchemaFormatter,
    SchemaFormatter,
    YamlSchemaFormatter,
)
from .handlers import (
    ClassSourceHandler,
    DataclassSourceHandler,
    JsonSourceHandler,
    PydanticSourceHandler,
    SqlAlchemySourceHandler,
    SourceHandler,
)

LOGGER = logging.getLogger(__name__)


class SchemaGenerator:
    """Generate schemas from various Neuroca data sources."""

    def __init__(self) -> None:
        """Initialise formatter and handler registries."""
        self._formatters: dict[SchemaFormat, SchemaFormatter] = {
            SchemaFormat.JSON: JsonSchemaFormatter(),
            SchemaFormat.YAML: YamlSchemaFormatter(),
            SchemaFormat.PROTOBUF: ProtobufSchemaFormatter(),
        }
        json_handler = JsonSourceHandler()
        self._handlers: dict[SourceType, SourceHandler] = {
            SourceType.PYDANTIC: PydanticSourceHandler(),
            SourceType.DATACLASS: DataclassSourceHandler(),
            SourceType.SQLALCHEMY: SqlAlchemySourceHandler(),
            SourceType.DICT: json_handler,
            SourceType.JSON: json_handler,
            SourceType.CLASS: ClassSourceHandler(),
        }

    def generate(
        self,
        source: Any,
        source_type: SourceType,
        output_format: SchemaFormat,
        output_path: Optional[str] = None,
        namespace: Optional[str] = None,
    ) -> Union[str, dict[str, Any]]:
        """Generate a schema from the provided source and format."""
        self._validate_source_type(source_type)
        self._validate_output_format(output_format)
        LOGGER.info("Generating %s schema from %s source", output_format.value, source_type.value)
        handler = self._get_handler(source_type)
        schema_data = handler.generate(source, namespace)
        formatter = self._get_formatter(output_format)
        formatted = formatter.format(schema_data)
        if output_path:
            self._write_schema(formatted, output_path, formatter.get_file_extension())
            return schema_data
        return formatted

    def _validate_source_type(self, source_type: SourceType) -> None:
        """Ensure a handler is registered for the given source type."""
        if source_type not in self._handlers:
            raise InvalidSourceError(f"Unsupported source type: {source_type}")

    def _validate_output_format(self, output_format: SchemaFormat) -> None:
        """Ensure a formatter is registered for the requested output format."""
        if output_format not in self._formatters:
            raise UnsupportedFormatError(f"Unsupported output format: {output_format}")

    def _get_handler(self, source_type: SourceType) -> SourceHandler:
        """Return the handler registered for the source type."""
        return self._handlers[source_type]

    def _get_formatter(self, output_format: SchemaFormat) -> SchemaFormatter:
        """Return the formatter registered for the output format."""
        return self._formatters[output_format]

    def _write_schema(self, schema: str, output_path: str, extension: str) -> None:
        """Persist the generated schema to disk."""
        try:
            target = Path(output_path)
            if target.is_dir():
                filename = f"schema_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}{extension}"
                target = target / filename
            elif target.suffix != extension:
                target = target.with_suffix(extension)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(schema, encoding="utf-8")
            LOGGER.info("Schema written to %s", target)
        except Exception as exc:  # noqa: BLE001
            LOGGER.error("Failed to write schema to %s: %s", output_path, exc)
            raise SchemaGenerationError(f"Failed to write schema: {exc}") from exc

    def available_source_types(self) -> list[SourceType]:
        """Return the list of registered source types."""
        return list(self._handlers.keys())

    def available_formats(self) -> list[SchemaFormat]:
        """Return the list of registered schema output formats."""
        return list(self._formatters.keys())


__all__ = ["SchemaGenerator"]
