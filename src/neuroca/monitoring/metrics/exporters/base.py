"""Base abstractions shared by all metrics exporters."""

from __future__ import annotations

import abc
import logging
import time
from typing import Any, Dict, List, Optional, Union

from .configuration_error import ConfigurationError
from .export_error import ExportError
from .metric_type import MetricType

__all__ = ["MetricExporter"]

logger = logging.getLogger(__name__)


class MetricExporter(abc.ABC):
    """Abstract base class implementing common batching logic for exporters."""

    def __init__(self, name: str, batch_size: int = 100, flush_interval: int = 60) -> None:
        """Initialise the exporter with batching behaviour."""
        if batch_size <= 0:
            raise ConfigurationError("batch_size must be a positive integer")
        if flush_interval <= 0:
            raise ConfigurationError("flush_interval must be a positive integer")

        self.name = name
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self.metrics_buffer: List[Dict[str, Any]] = []
        self.last_flush_time = time.time()
        self._initialized = False

        logger.debug(
            "Initialised %s '%s' with batch_size=%s flush_interval=%ss",
            self.__class__.__name__,
            name,
            batch_size,
            flush_interval,
        )

    @abc.abstractmethod
    def initialize(self) -> None:
        """Initialise exporter resources such as connections or background tasks."""

    @abc.abstractmethod
    def _export_batch(self, metrics: List[Dict[str, Any]]) -> None:
        """Send a batch of metrics to the backing monitoring system."""

    def export_metric(
        self,
        name: str,
        value: Union[int, float],
        labels: Optional[Dict[str, str]] = None,
        metric_type: MetricType = MetricType.GAUGE,
        timestamp: Optional[float] = None,
    ) -> None:
        """Queue a metric for export, flushing when thresholds are reached."""
        self._ensure_initialised()
        metric = self._build_metric(name, value, labels, metric_type, timestamp)
        self.metrics_buffer.append(metric)
        logger.debug("Queued metric: %s=%s (%s)", name, value, metric_type.value)

        if self._should_flush():
            self.flush()

    def flush(self) -> None:
        """Flush buffered metrics to the monitoring backend."""
        if not self.metrics_buffer:
            logger.debug("No metrics to flush")
            return

        metrics_to_export = self.metrics_buffer.copy()
        self.metrics_buffer.clear()

        try:
            logger.debug("Flushing %s metrics", len(metrics_to_export))
            self._export_batch(metrics_to_export)
            self.last_flush_time = time.time()
            logger.debug("Successfully flushed %s metrics", len(metrics_to_export))
        except Exception as exc:  # pragma: no cover - defensive restore path
            self.metrics_buffer.extend(metrics_to_export)
            logger.error("Failed to flush metrics: %s", exc)
            raise ExportError(f"Failed to export metrics: {exc}") from exc

    def close(self) -> None:
        """Flush any remaining metrics and mark the exporter as closed."""
        try:
            if self.metrics_buffer:
                logger.info("Flushing %s metrics before closing", len(self.metrics_buffer))
                self.flush()
        except Exception as exc:  # pragma: no cover - shutdown best effort
            logger.error("Error during final flush: %s", exc)

        logger.info("Closed %s '%s'", self.__class__.__name__, self.name)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_initialised(self) -> None:
        """Initialise the exporter lazily on first metric submission."""
        if not self._initialized:
            self.initialize()
            self._initialized = True

    def _build_metric(
        self,
        name: str,
        value: Union[int, float],
        labels: Optional[Dict[str, str]],
        metric_type: MetricType,
        timestamp: Optional[float],
    ) -> Dict[str, Any]:
        """Validate inputs and construct the buffered metric payload."""
        if not name or not isinstance(name, str):
            raise ValueError("Metric name must be a non-empty string")
        if not isinstance(value, (int, float)):
            raise ValueError(f"Metric value must be numeric, got {type(value)}")
        if labels is not None and not isinstance(labels, dict):
            raise ValueError(f"Labels must be a dictionary, got {type(labels)}")

        metric_timestamp = timestamp or time.time()
        safe_labels = dict(labels or {})
        return {
            "name": name,
            "value": value,
            "type": metric_type.value,
            "timestamp": metric_timestamp,
            "labels": safe_labels,
        }

    def _should_flush(self) -> bool:
        """Return ``True`` when buffered metrics should be flushed."""
        return len(self.metrics_buffer) >= self.batch_size or (
            time.time() - self.last_flush_time
        ) >= self.flush_interval
