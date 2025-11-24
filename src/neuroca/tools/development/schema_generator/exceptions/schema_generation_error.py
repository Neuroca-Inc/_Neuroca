"""Base exception for schema generation failures."""


class SchemaGenerationError(Exception):
    """Raised when schema generation cannot be completed successfully."""


__all__ = ["SchemaGenerationError"]
