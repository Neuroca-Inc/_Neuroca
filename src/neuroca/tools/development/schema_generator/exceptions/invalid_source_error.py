"""Exception raised when schema sources are invalid."""

from .schema_generation_error import SchemaGenerationError


class InvalidSourceError(SchemaGenerationError):
    """Raised when the provided source cannot be processed."""


__all__ = ["InvalidSourceError"]
