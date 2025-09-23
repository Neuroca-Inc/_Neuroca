"""Metrics exporter that persists batches to a JSON file."""

from __future__ import annotations

import json
import logging
import os
from typing import Any, List

from .configuration_error import ConfigurationError
from .export_error import ExportError
from .base import MetricExporter

__all__ = ["JsonFileExporter"]

logger = logging.getLogger(__name__)


class JsonFileExporter(MetricExporter):
    """Write exported metrics to disk as JSON documents."""

    def __init__(
        self,
        name: str = "json_file",
        file_path: str = "metrics.json",
        append: bool = True,
        **kwargs: Any,
    ) -> None:
        """Create the exporter and verify filesystem access."""
        super().__init__(name=name, **kwargs)

        self.file_path = file_path
        self.append = append
        self._ensure_destination()
        logger.info("Created JSON file exporter writing to %s (append=%s)", file_path, append)

    def initialize(self) -> None:
        """Prepare the JSON file for writing metrics."""
        if not self.append:
            self._initialise_empty_file()
        self._initialized = True
        logger.debug("Initialized JSON file exporter to %s", self.file_path)

    def _export_batch(self, metrics: list[dict[str, Any]]) -> None:
        """Persist the provided metrics batch to disk."""
        try:
            existing = self._load_existing_metrics()
            combined = existing + metrics
            self._write_metrics(combined)
            logger.debug("Exported %s metrics to %s", len(metrics), self.file_path)
        except Exception as exc:
            logger.error("Failed to export metrics to JSON file: %s", exc)
            raise ExportError(f"Failed to export metrics to JSON file: {exc}") from exc

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_destination(self) -> None:
        """Validate that the target directory exists and is writable."""
        directory = os.path.dirname(self.file_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory)

        mode = "a" if self.append else "w"
        try:
            with open(self.file_path, mode, encoding="utf-8"):
                pass
        except Exception as exc:
            raise ConfigurationError(
                f"Cannot access metrics file {self.file_path}: {exc}"
            ) from exc

    def _initialise_empty_file(self) -> None:
        """Initialise the metrics file with an empty list."""
        try:
            with open(self.file_path, "w", encoding="utf-8") as handle:
                json.dump([], handle)
        except Exception as exc:
            raise ConfigurationError(f"Failed to initialise metrics file: {exc}") from exc

    def _load_existing_metrics(self) -> List[dict[str, Any]]:
        """Load metrics already persisted on disk if available."""
        if not self.append:
            return []

        if not os.path.exists(self.file_path) or os.path.getsize(self.file_path) == 0:
            return []

        try:
            with open(self.file_path, encoding="utf-8") as handle:
                return list(json.load(handle))
        except json.JSONDecodeError:
            logger.warning(
                "Could not parse existing metrics file %s, overwriting", self.file_path
            )
            return []

    def _write_metrics(self, metrics: List[dict[str, Any]]) -> None:
        """Write the provided metrics to the target file."""
        with open(self.file_path, "w", encoding="utf-8") as handle:
            json.dump(metrics, handle, indent=2)
