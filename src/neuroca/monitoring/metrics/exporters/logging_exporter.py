"""Logging-based metrics exporter for development environments."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from .base import MetricExporter

__all__ = ["LoggingExporter"]

logger = logging.getLogger(__name__)


class LoggingExporter(MetricExporter):
    """Export metrics by writing structured log entries."""

    def __init__(
        self,
        name: str = "logging",
        logger_name: Optional[str] = None,
        log_level: int = logging.INFO,
        **kwargs: Any,
    ) -> None:
        """Initialise the logging exporter with the desired log level."""
        super().__init__(name=name, **kwargs)
        self.log_level = log_level
        self.metrics_logger = logging.getLogger(logger_name or __name__)
        logger.info("Created logging exporter with log_level=%s", log_level)

    def initialize(self) -> None:
        """Mark the logging exporter as ready for use."""
        self._initialized = True
        logger.debug("Initialized logging exporter")

    def _export_batch(self, metrics: list[dict[str, Any]]) -> None:
        """Log each metric in the batch at the configured log level."""
        for metric in metrics:
            message = self._format_message(metric)
            self.metrics_logger.log(self.log_level, message)
        logger.debug("Logged %s metrics at level %s", len(metrics), self.log_level)

    def _format_message(self, metric: Dict[str, Any]) -> str:
        """Return a formatted string representing the metric payload."""
        labels = metric["labels"]
        labels_str = ", ".join(f"{key}={value}" for key, value in labels.items()) if labels else ""
        base = f"METRIC: {metric['name']}={metric['value']} ({metric['type']})"
        return f"{base} [{labels_str}]" if labels_str else base
