"""Common primitives used by all metrics collectors."""

from __future__ import annotations

import abc
import logging
import time
from typing import Optional, Union

from neuroca.monitoring.metrics.models import (
    Metric,
    MetricLabel,
    MetricType,
    MetricUnit,
    MetricValue,
)

logger = logging.getLogger(__name__)


class BaseMetricsCollector(abc.ABC):
    """Abstract interface shared by all metrics collectors."""

    def __init__(
        self,
        name: str,
        enabled: bool = True,
        collection_interval: float = 60.0,
        metrics_prefix: str = "neuroca",
    ):
        """Initialize a collector scaffold.

        Args:
            name: Unique name for this collector.
            enabled: Whether the collector starts enabled.
            collection_interval: Minimum seconds between collections.
            metrics_prefix: Prefix applied to every metric emitted by the collector.
        """
        self.name = name
        self.enabled = enabled
        self.collection_interval = collection_interval
        self.last_collection_time = 0.0
        self.metrics_prefix = metrics_prefix

        logger.debug("Initialized collector %s", name)

    @abc.abstractmethod
    def collect(self) -> list[Metric]:
        """Collect metrics and return them as a list."""

    def should_collect(self) -> bool:
        """Return ``True`` when the collection interval has elapsed."""
        if not self.enabled:
            return False

        current_time = time.time()
        return current_time - self.last_collection_time >= self.collection_interval

    def format_metric_name(self, name: str) -> str:
        """Return a prefixed metric name for the provided suffix."""
        return f"{self.metrics_prefix}.{self.name}.{name}"

    def create_metric(
        self,
        name: str,
        value: Union[int, float, str, bool],
        metric_type: MetricType,
        unit: Optional[MetricUnit] = None,
        labels: Optional[dict[str, str]] = None,
        description: Optional[str] = None,
        timestamp: Optional[float] = None,
    ) -> Metric:
        """Build a :class:`~neuroca.monitoring.metrics.models.Metric` instance."""
        metric_name = self.format_metric_name(name)
        metric_value = MetricValue(value=value)
        metric_labels = []

        if labels:
            metric_labels = [MetricLabel(name=k, value=v) for k, v in labels.items()]

        return Metric(
            name=metric_name,
            value=metric_value,
            type=metric_type,
            unit=unit,
            labels=metric_labels,
            description=description or f"{name} metric",
            timestamp=timestamp or time.time(),
        )
