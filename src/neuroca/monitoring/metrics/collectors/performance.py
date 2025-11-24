"""Performance metrics collector."""

from __future__ import annotations

import logging
import time

from neuroca.config import settings
from neuroca.core.exceptions import MetricsCollectionError
from neuroca.monitoring.metrics.models import Metric, MetricType, MetricUnit

from .base import BaseMetricsCollector

logger = logging.getLogger(__name__)


class PerformanceMetricsCollector(BaseMetricsCollector):
    """Collect placeholder throughput and latency metrics across subsystems."""

    def __init__(
        self,
        name: str = "performance",
        enabled: bool = True,
        collection_interval: float = 30.0,
        metrics_prefix: str = "neuroca",
    ):
        """Initialize the performance collector with shared labels."""
        super().__init__(name, enabled, collection_interval, metrics_prefix)
        self.performance_labels = {
            "component": "performance",
            "version": settings.get("system.version", "unknown"),
        }

        logger.debug("PerformanceMetricsCollector initialized")

    def collect(self) -> list[Metric]:
        """Collect metrics describing API, processing, and memory performance."""
        if not self.should_collect():
            return []

        try:
            metrics: list[Metric] = []
            metrics.extend(self._collect_api_performance_metrics())
            metrics.extend(self._collect_processing_performance_metrics())
            metrics.extend(self._collect_memory_performance_metrics())

            self.last_collection_time = time.time()
            logger.debug("Collected %s performance metrics", len(metrics))
            return metrics

        except Exception as exc:  # noqa: BLE001 - escalate as MetricsCollectionError
            error_msg = f"Failed to collect performance metrics: {exc}".rstrip()
            logger.error(error_msg, exc_info=True)
            raise MetricsCollectionError(error_msg) from exc

    def _collect_api_performance_metrics(self) -> list[Metric]:
        """Collect API focused metrics."""
        metrics: list[Metric] = []
        api_labels = {**self.performance_labels, "subsystem": "api"}

        metrics.append(
            self.create_metric(
                name="api.requests.rate",
                value=25.5,
                metric_type=MetricType.GAUGE,
                unit=MetricUnit.RATE_PER_SECOND,
                labels=api_labels,
                description="API request rate per second",
            )
        )
        metrics.append(
            self.create_metric(
                name="api.response_time.avg",
                value=0.12,
                metric_type=MetricType.GAUGE,
                unit=MetricUnit.SECONDS,
                labels=api_labels,
                description="Average API response time",
            )
        )
        metrics.append(
            self.create_metric(
                name="api.response_time.p95",
                value=0.25,
                metric_type=MetricType.GAUGE,
                unit=MetricUnit.SECONDS,
                labels=api_labels,
                description="95th percentile API response time",
            )
        )
        metrics.append(
            self.create_metric(
                name="api.error_rate",
                value=0.02,
                metric_type=MetricType.GAUGE,
                unit=MetricUnit.PERCENT,
                labels=api_labels,
                description="API error rate",
            )
        )

        return metrics

    def _collect_processing_performance_metrics(self) -> list[Metric]:
        """Collect background processing metrics."""
        metrics: list[Metric] = []
        processing_labels = {**self.performance_labels, "subsystem": "processing"}

        metrics.append(
            self.create_metric(
                name="processing.queue.length",
                value=75,
                metric_type=MetricType.GAUGE,
                unit=MetricUnit.COUNT,
                labels=processing_labels,
                description="Number of tasks waiting in the processing queue",
            )
        )
        metrics.append(
            self.create_metric(
                name="processing.queue.wait_time",
                value=1.5,
                metric_type=MetricType.GAUGE,
                unit=MetricUnit.SECONDS,
                labels=processing_labels,
                description="Average wait time in the processing queue",
            )
        )

        task_types = ["classification", "summarization", "embedding", "routing"]
        for task_type in task_types:
            task_labels = {**processing_labels, "task": task_type}
            metrics.append(
                self.create_metric(
                    name="processing.task.count",
                    value=50,
                    metric_type=MetricType.COUNTER,
                    unit=MetricUnit.COUNT,
                    labels=task_labels,
                    description=f"Total {task_type} tasks processed",
                )
            )
            metrics.append(
                self.create_metric(
                    name="processing.task.duration",
                    value=0.15,
                    metric_type=MetricType.GAUGE,
                    unit=MetricUnit.SECONDS,
                    labels=task_labels,
                    description=f"Average duration of {task_type} tasks",
                )
            )

        return metrics

    def _collect_memory_performance_metrics(self) -> list[Metric]:
        """Collect memory subsystem performance metrics."""
        metrics: list[Metric] = []
        memory_labels = {**self.performance_labels, "subsystem": "memory"}

        metrics.append(
            self.create_metric(
                name="memory.access.rate",
                value=45.8,
                metric_type=MetricType.GAUGE,
                unit=MetricUnit.RATE_PER_SECOND,
                labels=memory_labels,
                description="Memory access rate per second",
            )
        )
        metrics.append(
            self.create_metric(
                name="memory.access.latency",
                value=0.05,
                metric_type=MetricType.GAUGE,
                unit=MetricUnit.SECONDS,
                labels=memory_labels,
                description="Average memory access latency",
            )
        )

        operation_types = ["read", "write", "update", "delete"]
        for operation in operation_types:
            op_labels = {**memory_labels, "operation": operation}
            metrics.append(
                self.create_metric(
                    name="memory.operation.count",
                    value=200,
                    metric_type=MetricType.COUNTER,
                    unit=MetricUnit.COUNT,
                    labels=op_labels,
                    description=f"Total {operation} operations on memory",
                )
            )
            metrics.append(
                self.create_metric(
                    name="memory.operation.latency",
                    value=0.03,
                    metric_type=MetricType.GAUGE,
                    unit=MetricUnit.SECONDS,
                    labels=op_labels,
                    description=f"Average latency of {operation} operations",
                )
            )

        memory_tiers = ["working", "episodic", "semantic"]
        for tier in memory_tiers:
            tier_labels = {**memory_labels, "tier": f"{tier}_memory"}
            metrics.append(
                self.create_metric(
                    name="memory.tier.access_rate",
                    value=15.0,
                    metric_type=MetricType.GAUGE,
                    unit=MetricUnit.RATE_PER_SECOND,
                    labels=tier_labels,
                    description=f"Access rate for {tier} memory tier",
                )
            )
            metrics.append(
                self.create_metric(
                    name="memory.tier.latency",
                    value=0.08,
                    metric_type=MetricType.GAUGE,
                    unit=MetricUnit.SECONDS,
                    labels=tier_labels,
                    description=f"Average latency for {tier} memory tier",
                )
            )

        return metrics
