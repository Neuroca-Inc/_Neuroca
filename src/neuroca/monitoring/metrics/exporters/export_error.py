"""Exception raised when exporting metrics fails."""

from __future__ import annotations

from .exporter_error import ExporterError

__all__ = ["ExportError"]


class ExportError(ExporterError):
    """Raised when an exporter cannot deliver metrics to its backend."""

    def __init__(self, message: str) -> None:
        """Initialise the export error with the failure description."""
        super().__init__(message)
