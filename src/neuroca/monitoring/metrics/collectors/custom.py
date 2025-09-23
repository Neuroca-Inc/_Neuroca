"""Custom metrics collector."""

from __future__ import annotations

import logging
import time
from typing import Any, Optional, Union

from neuroca.core.exceptions import MetricsCollectionError
from neuroca.monitoring.metrics.models import Metric, MetricType, MetricUnit

from .base import BaseMetricsCollector

logger = logging.getLogger(__name__)


class CustomMetricsCollector(BaseMetricsCollector):
    """Allow users to register and emit bespoke metrics at runtime."""

    def __init__(
        self,
        name: str = "custom",
        enabled: bool = True,
        collection_interval: float = 60.0,
        metrics_prefix: str = "neuroca",
    ):
        """Initialize the custom collector with empty metric storage."""
        super().__init__(name, enabled, collection_interval, metrics_prefix)
        self._custom_metrics: dict[str, dict[str, Any]] = {}

        logger.debug("CustomMetricsCollector initialized")

    def register_metric(
        self,
        name: str,
        metric_type: MetricType,
        description: str,
        unit: Optional[MetricUnit] = None,
        labels: Optional[dict[str, str]] = None,
    ) -> None:
        """Register a new custom metric definition."""
        if name in self._custom_metrics:
            raise ValueError(f"Metric with name '{name}' already exists")

        self._custom_metrics[name] = {
            "type": metric_type,
            "description": description,
            "unit": unit,
            "labels": labels or {},
            "value": None,
            "last_updated": None,
        }

        logger.debug("Registered custom metric '%s'", name)

    def update_metric(
        self,
        name: str,
        value: Union[int, float, str, bool],
        labels: Optional[dict[str, str]] = None,
    ) -> None:
        """Update the stored value for a custom metric."""
        if name not in self._custom_metrics:
            raise ValueError(f"Metric with name '{name}' does not exist")

        self._custom_metrics[name]["value"] = value
        self._custom_metrics[name]["last_updated"] = time.time()

        if labels:
            self._custom_metrics[name]["labels"].update(labels)

        logger.debug("Updated custom metric '%s' with value %s", name, value)

    def collect(self) -> list[Metric]:
        """Collect all registered custom metrics."""
        if not self.should_collect():
            return []

        try:
            metrics: list[Metric] = []
            for name, metric_data in self._custom_metrics.items():
                if metric_data["value"] is None:
                    continue

                metrics.append(
                    self.create_metric(
                        name=name,
                        value=metric_data["value"],
                        metric_type=metric_data["type"],
                        unit=metric_data["unit"],
                        labels=metric_data["labels"],
                        description=metric_data["description"],
                        timestamp=metric_data["last_updated"],
                    )
                )

            self.last_collection_time = time.time()
            logger.debug("Collected %s custom metrics", len(metrics))
            return metrics

        except Exception as exc:  # noqa: BLE001 - escalate as MetricsCollectionError
            error_msg = f"Failed to collect custom metrics: {exc}".rstrip()
            logger.error(error_msg, exc_info=True)
            raise MetricsCollectionError(error_msg) from exc

    def reset_metric(self, name: str) -> None:
        """Reset a counter metric to zero."""
        if name not in self._custom_metrics:
            raise ValueError(f"Metric with name '{name}' does not exist")

        if self._custom_metrics[name]["type"] != MetricType.COUNTER:
            raise ValueError(f"Metric '{name}' is not a counter and cannot be reset")

        self._custom_metrics[name]["value"] = 0
        self._custom_metrics[name]["last_updated"] = time.time()

        logger.debug("Reset counter metric '%s' to zero", name)

    def increment_counter(self, name: str, value: float = 1.0) -> None:
        """Increment a counter metric by ``value``."""
        if name not in self._custom_metrics:
            raise ValueError(f"Metric with name '{name}' does not exist")

        if self._custom_metrics[name]["type"] != MetricType.COUNTER:
            raise ValueError(f"Metric '{name}' is not a counter and cannot be incremented")

        current_value = self._custom_metrics[name]["value"] or 0
        self._custom_metrics[name]["value"] = current_value + value
        self._custom_metrics[name]["last_updated"] = time.time()

        logger.debug("Incremented counter metric '%s' by %s", name, value)

    def remove_metric(self, name: str) -> None:
        """Remove a registered custom metric."""
        if name not in self._custom_metrics:
            raise ValueError(f"Metric with name '{name}' does not exist")

        del self._custom_metrics[name]
        logger.debug("Removed custom metric '%s'", name)
