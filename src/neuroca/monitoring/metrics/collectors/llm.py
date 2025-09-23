"""LLM integration metrics collector."""

from __future__ import annotations

import logging
import time

from neuroca.config import settings
from neuroca.core.exceptions import MetricsCollectionError
from neuroca.monitoring.metrics.models import Metric, MetricType, MetricUnit

from .base import BaseMetricsCollector

logger = logging.getLogger(__name__)


class LLMIntegrationMetricsCollector(BaseMetricsCollector):
    """Collect placeholder metrics describing external LLM integrations."""

    def __init__(
        self,
        name: str = "llm_integration",
        enabled: bool = True,
        collection_interval: float = 60.0,
        metrics_prefix: str = "neuroca",
    ):
        """Initialize the LLM metrics collector."""
        super().__init__(name, enabled, collection_interval, metrics_prefix)
        self.llm_labels = {
            "component": "llm_integration",
            "version": settings.get("llm.integration.version", "unknown"),
        }

        logger.debug("LLMIntegrationMetricsCollector initialized")

    def collect(self) -> list[Metric]:
        """Collect metrics across known providers."""
        if not self.should_collect():
            return []

        try:
            metrics: list[Metric] = []
            providers = ["openai", "anthropic", "local"]

            for provider in providers:
                metrics.extend(self._collect_provider_metrics(provider))

            self.last_collection_time = time.time()
            logger.debug("Collected %s LLM integration metrics", len(metrics))
            return metrics

        except Exception as exc:  # noqa: BLE001 - escalate as MetricsCollectionError
            error_msg = f"Failed to collect LLM integration metrics: {exc}".rstrip()
            logger.error(error_msg, exc_info=True)
            raise MetricsCollectionError(error_msg) from exc

    def _collect_provider_metrics(self, provider: str) -> list[Metric]:
        """Collect metrics for a specific LLM provider."""
        metrics: list[Metric] = []
        provider_labels = {**self.llm_labels, "provider": provider}

        metrics.append(
            self.create_metric(
                name="llm.requests.total",
                value=500,
                metric_type=MetricType.COUNTER,
                unit=MetricUnit.COUNT,
                labels=provider_labels,
                description=f"Total number of requests to {provider}",
            )
        )
        metrics.append(
            self.create_metric(
                name="llm.requests.successful",
                value=480,
                metric_type=MetricType.COUNTER,
                unit=MetricUnit.COUNT,
                labels=provider_labels,
                description=f"Number of successful requests to {provider}",
            )
        )
        metrics.append(
            self.create_metric(
                name="llm.requests.failed",
                value=20,
                metric_type=MetricType.COUNTER,
                unit=MetricUnit.COUNT,
                labels=provider_labels,
                description=f"Number of failed requests to {provider}",
            )
        )
        metrics.append(
            self.create_metric(
                name="llm.latency.avg",
                value=1.2,
                metric_type=MetricType.GAUGE,
                unit=MetricUnit.SECONDS,
                labels=provider_labels,
                description=f"Average request latency for {provider}",
            )
        )
        metrics.append(
            self.create_metric(
                name="llm.latency.p95",
                value=2.5,
                metric_type=MetricType.GAUGE,
                unit=MetricUnit.SECONDS,
                labels=provider_labels,
                description=f"95th percentile request latency for {provider}",
            )
        )
        metrics.append(
            self.create_metric(
                name="llm.latency.p99",
                value=4.0,
                metric_type=MetricType.GAUGE,
                unit=MetricUnit.SECONDS,
                labels=provider_labels,
                description=f"99th percentile request latency for {provider}",
            )
        )
        metrics.append(
            self.create_metric(
                name="llm.tokens.input",
                value=25000,
                metric_type=MetricType.COUNTER,
                unit=MetricUnit.COUNT,
                labels=provider_labels,
                description=f"Total input tokens sent to {provider}",
            )
        )
        metrics.append(
            self.create_metric(
                name="llm.tokens.output",
                value=120000,
                metric_type=MetricType.COUNTER,
                unit=MetricUnit.COUNT,
                labels=provider_labels,
                description=f"Total output tokens received from {provider}",
            )
        )

        if provider in {"openai", "anthropic"}:
            metrics.append(
                self.create_metric(
                    name="llm.cost",
                    value=2.35,
                    metric_type=MetricType.COUNTER,
                    unit=MetricUnit.USD,
                    labels=provider_labels,
                    description=f"Total cost of requests to {provider}",
                )
            )

        metrics.append(
            self.create_metric(
                name="llm.rate_limits.hit",
                value=5,
                metric_type=MetricType.COUNTER,
                unit=MetricUnit.COUNT,
                labels=provider_labels,
                description=f"Number of rate limit hits for {provider}",
            )
        )

        models = self._get_models_for_provider(provider)
        for model in models:
            model_labels = {**provider_labels, "model": model}
            metrics.append(
                self.create_metric(
                    name="llm.model.requests",
                    value=100,
                    metric_type=MetricType.COUNTER,
                    unit=MetricUnit.COUNT,
                    labels=model_labels,
                    description=f"Number of requests to {model} model",
                )
            )
            metrics.append(
                self.create_metric(
                    name="llm.model.latency",
                    value=0.8,
                    metric_type=MetricType.GAUGE,
                    unit=MetricUnit.SECONDS,
                    labels=model_labels,
                    description=f"Average latency for {model} model",
                )
            )

        return metrics

    def _get_models_for_provider(self, provider: str) -> list[str]:
        """Return configured models for the requested provider."""
        provider_models = {
            "openai": ["gpt-4", "gpt-3.5-turbo"],
            "anthropic": ["claude-2", "claude-instant"],
            "local": ["llama-2-7b", "mistral-7b"],
        }
        return provider_models.get(provider, [])
