"""Registry for orchestrating metrics collectors."""

from __future__ import annotations

import logging

from neuroca.monitoring.metrics.models import Metric

from .base import BaseMetricsCollector

logger = logging.getLogger(__name__)


class MetricsCollectorRegistry:
    """Manage a collection of :class:`BaseMetricsCollector` instances."""

    def __init__(self) -> None:
        """Initialise an empty collector registry."""
        self._collectors: dict[str, BaseMetricsCollector] = {}
        logger.debug("MetricsCollectorRegistry initialized")

    def register(self, collector: BaseMetricsCollector) -> None:
        """Register ``collector`` by its name."""
        if collector.name in self._collectors:
            raise ValueError(f"Collector with name '{collector.name}' already exists")

        self._collectors[collector.name] = collector
        logger.debug("Registered collector '%s'", collector.name)

    def unregister(self, name: str) -> None:
        """Remove the collector identified by ``name``."""
        if name not in self._collectors:
            raise ValueError(f"Collector with name '{name}' does not exist")

        del self._collectors[name]
        logger.debug("Unregistered collector '%s'", name)

    def get_collector(self, name: str) -> BaseMetricsCollector:
        """Return the collector registered under ``name``."""
        if name not in self._collectors:
            raise ValueError(f"Collector with name '{name}' does not exist")

        return self._collectors[name]

    def collect_all(self) -> list[Metric]:
        """Collect metrics from every registered collector."""
        all_metrics: list[Metric] = []

        for name, collector in self._collectors.items():
            try:
                if collector.enabled:
                    metrics = collector.collect()
                    all_metrics.extend(metrics)
                    logger.debug("Collected %s metrics from '%s'", len(metrics), name)
            except Exception as exc:  # noqa: BLE001 - log and continue
                logger.error("Failed to collect metrics from '%s': %s", name, exc, exc_info=True)

        logger.info("Collected a total of %s metrics from all collectors", len(all_metrics))
        return all_metrics

    def get_collector_names(self) -> list[str]:
        """Return the names of all registered collectors."""
        return list(self._collectors.keys())

    def enable_collector(self, name: str) -> None:
        """Enable the collector referenced by ``name``."""
        collector = self.get_collector(name)
        collector.enabled = True
        logger.debug("Enabled collector '%s'", name)

    def disable_collector(self, name: str) -> None:
        """Disable the collector referenced by ``name``."""
        collector = self.get_collector(name)
        collector.enabled = False
        logger.debug("Disabled collector '%s'", name)

    def set_collection_interval(self, name: str, interval: float) -> None:
        """Update the collection interval for ``name``."""
        if interval <= 0:
            raise ValueError("Collection interval must be positive")

        collector = self.get_collector(name)
        collector.collection_interval = interval
        logger.debug("Set collection interval for '%s' to %s seconds", name, interval)
