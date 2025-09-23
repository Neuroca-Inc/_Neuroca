"""Abstract base class for schema formatters."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class SchemaFormatter(ABC):
    """Interface for schema formatters that render schema dictionaries."""

    @abstractmethod
    def format(self, schema_data: dict[str, Any]) -> str:
        """Format the schema data into the formatter's output representation."""

    @abstractmethod
    def get_file_extension(self) -> str:
        """Return the file extension associated with the formatter's output."""


__all__ = ["SchemaFormatter"]
