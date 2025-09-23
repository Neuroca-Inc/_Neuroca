"""Base exception for monitoring metrics exporters."""

from __future__ import annotations

__all__ = ["ExporterError"]


class ExporterError(Exception):
    """Base exception class for all exporter-related errors."""

    def __init__(self, message: str) -> None:
        """Store the message describing the exporter failure."""
        super().__init__(message)
