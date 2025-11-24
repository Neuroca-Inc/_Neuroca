"""Memory tier metrics collector."""

from __future__ import annotations

import logging
import time

from neuroca.config import settings
from neuroca.core.exceptions import MetricsCollectionError
from neuroca.monitoring.metrics.models import Metric, MetricType, MetricUnit

from .base import BaseMetricsCollector

logger = logging.getLogger(__name__)


class MemoryTierMetricsCollector(BaseMetricsCollector):
    """Collect placeholder metrics for working, episodic, and semantic tiers."""

    def __init__(
        self,
        name: str = "memory_tiers",
        enabled: bool = True,
        collection_interval: float = 30.0,
        metrics_prefix: str = "neuroca",
    ):
        """Initialize the tier collector with shared labels."""
        super().__init__(name, enabled, collection_interval, metrics_prefix)
        self.memory_labels = {
            "component": "memory_system",
            "version": settings.get("memory.version", "unknown"),
        }

        logger.debug("MemoryTierMetricsCollector initialized")

    def collect(self) -> list[Metric]:
        """Collect metrics for each logical memory tier."""
        if not self.should_collect():
            return []

        try:
            metrics: list[Metric] = []
            metrics.extend(self._collect_working_memory_metrics())
            metrics.extend(self._collect_episodic_memory_metrics())
            metrics.extend(self._collect_semantic_memory_metrics())

            self.last_collection_time = time.time()
            logger.debug("Collected %s memory tier metrics", len(metrics))
            return metrics

        except Exception as exc:  # noqa: BLE001 - escalate as MetricsCollectionError
            error_msg = f"Failed to collect memory tier metrics: {exc}".rstrip()
            logger.error(error_msg, exc_info=True)
            raise MetricsCollectionError(error_msg) from exc

    def _collect_working_memory_metrics(self) -> list[Metric]:
        """Collect working memory metrics."""
        metrics: list[Metric] = []
        working_labels = {**self.memory_labels, "tier": "working_memory"}

        metrics.append(
            self.create_metric(
                name="memory.working.size",
                value=100,
                metric_type=MetricType.GAUGE,
                unit=MetricUnit.COUNT,
                labels=working_labels,
                description="Current number of items in working memory",
            )
        )
        metrics.append(
            self.create_metric(
                name="memory.working.capacity",
                value=150,
                metric_type=MetricType.GAUGE,
                unit=MetricUnit.COUNT,
                labels=working_labels,
                description="Maximum capacity of working memory",
            )
        )
        metrics.append(
            self.create_metric(
                name="memory.working.reads",
                value=250,
                metric_type=MetricType.COUNTER,
                unit=MetricUnit.COUNT,
                labels=working_labels,
                description="Total number of read operations from working memory",
            )
        )
        metrics.append(
            self.create_metric(
                name="memory.working.writes",
                value=120,
                metric_type=MetricType.COUNTER,
                unit=MetricUnit.COUNT,
                labels=working_labels,
                description="Total number of write operations to working memory",
            )
        )
        metrics.append(
            self.create_metric(
                name="memory.working.read_latency",
                value=0.005,
                metric_type=MetricType.GAUGE,
                unit=MetricUnit.SECONDS,
                labels=working_labels,
                description="Average read latency for working memory",
            )
        )
        metrics.append(
            self.create_metric(
                name="memory.working.write_latency",
                value=0.007,
                metric_type=MetricType.GAUGE,
                unit=MetricUnit.SECONDS,
                labels=working_labels,
                description="Average write latency for working memory",
            )
        )

        return metrics

    def _collect_episodic_memory_metrics(self) -> list[Metric]:
        """Collect episodic memory metrics."""
        metrics: list[Metric] = []
        episodic_labels = {**self.memory_labels, "tier": "episodic_memory"}

        metrics.append(
            self.create_metric(
                name="memory.episodic.events",
                value=10000,
                metric_type=MetricType.GAUGE,
                unit=MetricUnit.COUNT,
                labels=episodic_labels,
                description="Number of episodic events stored",
            )
        )
        metrics.append(
            self.create_metric(
                name="memory.episodic.size_bytes",
                value=50000000,
                metric_type=MetricType.GAUGE,
                unit=MetricUnit.BYTES,
                labels=episodic_labels,
                description="Total storage size of episodic memory",
            )
        )
        metrics.append(
            self.create_metric(
                name="memory.episodic.retrievals",
                value=2000,
                metric_type=MetricType.COUNTER,
                unit=MetricUnit.COUNT,
                labels=episodic_labels,
                description="Total number of episodic memory retrievals",
            )
        )
        metrics.append(
            self.create_metric(
                name="memory.episodic.stores",
                value=800,
                metric_type=MetricType.COUNTER,
                unit=MetricUnit.COUNT,
                labels=episodic_labels,
                description="Total number of episodic memory stores",
            )
        )
        metrics.append(
            self.create_metric(
                name="memory.episodic.retrieval_latency",
                value=0.15,
                metric_type=MetricType.GAUGE,
                unit=MetricUnit.SECONDS,
                labels=episodic_labels,
                description="Average retrieval latency for episodic memory",
            )
        )
        metrics.append(
            self.create_metric(
                name="memory.episodic.store_latency",
                value=0.2,
                metric_type=MetricType.GAUGE,
                unit=MetricUnit.SECONDS,
                labels=episodic_labels,
                description="Average store latency for episodic memory",
            )
        )
        metrics.append(
            self.create_metric(
                name="memory.episodic.retrieval_success_rate",
                value=0.95,
                metric_type=MetricType.GAUGE,
                unit=MetricUnit.PERCENT,
                labels=episodic_labels,
                description="Success rate of episodic memory retrievals",
            )
        )

        return metrics

    def _collect_semantic_memory_metrics(self) -> list[Metric]:
        """Collect semantic memory metrics."""
        metrics: list[Metric] = []
        semantic_labels = {**self.memory_labels, "tier": "semantic_memory"}

        metrics.append(
            self.create_metric(
                name="memory.semantic.concepts",
                value=50000,
                metric_type=MetricType.GAUGE,
                unit=MetricUnit.COUNT,
                labels=semantic_labels,
                description="Number of concepts in semantic memory",
            )
        )
        metrics.append(
            self.create_metric(
                name="memory.semantic.relationships",
                value=200000,
                metric_type=MetricType.GAUGE,
                unit=MetricUnit.COUNT,
                labels=semantic_labels,
                description="Number of relationships in semantic memory",
            )
        )
        metrics.append(
            self.create_metric(
                name="memory.semantic.storage_bytes",
                value=150000000,
                metric_type=MetricType.GAUGE,
                unit=MetricUnit.BYTES,
                labels=semantic_labels,
                description="Storage size of semantic memory in bytes",
            )
        )
        metrics.append(
            self.create_metric(
                name="memory.semantic.queries",
                value=1200,
                metric_type=MetricType.COUNTER,
                unit=MetricUnit.COUNT,
                labels=semantic_labels,
                description="Total number of semantic memory queries",
            )
        )
        metrics.append(
            self.create_metric(
                name="memory.semantic.updates",
                value=300,
                metric_type=MetricType.COUNTER,
                unit=MetricUnit.COUNT,
                labels=semantic_labels,
                description="Total number of semantic memory updates",
            )
        )
        metrics.append(
            self.create_metric(
                name="memory.semantic.query_latency",
                value=0.25,
                metric_type=MetricType.GAUGE,
                unit=MetricUnit.SECONDS,
                labels=semantic_labels,
                description="Average query latency for semantic memory",
            )
        )
        metrics.append(
            self.create_metric(
                name="memory.semantic.update_latency",
                value=0.15,
                metric_type=MetricType.GAUGE,
                unit=MetricUnit.SECONDS,
                labels=semantic_labels,
                description="Average update latency for semantic memory",
            )
        )

        return metrics
