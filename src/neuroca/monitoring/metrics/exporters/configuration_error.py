"""Exception raised when an exporter configuration is invalid."""

from __future__ import annotations

from .exporter_error import ExporterError

__all__ = ["ConfigurationError"]


class ConfigurationError(ExporterError):
    """Raised when metrics exporters receive invalid configuration."""

    def __init__(self, message: str) -> None:
        """Initialise the configuration error with a descriptive message."""
        super().__init__(message)
