"""Exception raised when unsupported schema formats are requested."""

from .schema_generation_error import SchemaGenerationError


class UnsupportedFormatError(SchemaGenerationError):
    """Raised when a schema format does not have a registered formatter."""


__all__ = ["UnsupportedFormatError"]
