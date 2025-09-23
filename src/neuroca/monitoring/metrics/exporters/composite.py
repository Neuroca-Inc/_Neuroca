"""Composite exporter that fans metrics out to multiple exporters."""

from __future__ import annotations

import logging
from typing import Any, Iterable, List

from .base import MetricExporter
from .configuration_error import ConfigurationError
from .export_error import ExportError

__all__ = ["CompositeExporter"]

logger = logging.getLogger(__name__)


class CompositeExporter(MetricExporter):
    """Forward metrics to a collection of sub-exporters."""

    def __init__(
        self,
        name: str = "composite",
        exporters: Iterable[MetricExporter] | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialise the composite exporter with optional sub-exporters."""
        super().__init__(name=name, **kwargs)
        self.exporters: List[MetricExporter] = list(exporters or [])
        exporter_names = [exporter.name for exporter in self.exporters]
        logger.info(
            "Created composite exporter with %s sub-exporters: %s",
            len(self.exporters),
            exporter_names,
        )

    def add_exporter(self, exporter: MetricExporter) -> None:
        """Append an exporter to the composite at runtime."""
        self.exporters.append(exporter)
        logger.debug(
            "Added %s '%s' to composite exporter",
            exporter.__class__.__name__,
            exporter.name,
        )

    def initialize(self) -> None:
        """Initialise all sub-exporters, collecting configuration errors."""
        errors: List[str] = []
        for exporter in self.exporters:
            try:
                if not exporter._initialized:
                    exporter.initialize()
            except Exception as exc:  # pragma: no cover - aggregated failures
                errors.append(f"{exporter.name}: {exc}")
                logger.error("Failed to initialise sub-exporter %s: %s", exporter.name, exc)

        if errors:
            raise ConfigurationError(
                f"Failed to initialise some sub-exporters: {'; '.join(errors)}"
            )

        self._initialized = True
        logger.debug("Initialized all %s sub-exporters", len(self.exporters))

    def _export_batch(self, metrics: list[dict[str, Any]]) -> None:
        """Propagate metrics to every configured exporter."""
        errors: List[str] = []
        for exporter in self.exporters:
            try:
                exporter._export_batch(metrics)
            except Exception as exc:
                errors.append(f"{exporter.name}: {exc}")
                logger.error("Sub-exporter %s failed to export metrics: %s", exporter.name, exc)

        if errors:
            raise ExportError(f"Some sub-exporters failed: {'; '.join(errors)}")

        logger.debug(
            "Exported %s metrics to %s sub-exporters", len(metrics), len(self.exporters)
        )

    def close(self) -> None:
        """Close each sub-exporter before delegating to the base class."""
        for exporter in self.exporters:
            try:
                exporter.close()
            except Exception as exc:  # pragma: no cover - shutdown best effort
                logger.error("Error closing sub-exporter %s: %s", exporter.name, exc)

        super().close()
