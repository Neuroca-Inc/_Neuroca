"""OpenTelemetry exporter implementation for Neuroca metrics."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple

from .configuration_error import ConfigurationError
from .export_error import ExportError
from .metric_type import MetricType
from .base import MetricExporter

__all__ = ["OPENTELEMETRY_AVAILABLE", "OpenTelemetryExporter"]

try:  # pragma: no cover - optional dependency detection
    from opentelemetry import metrics as otel_metrics
    from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader

    OPENTELEMETRY_AVAILABLE = True
except ImportError:  # pragma: no cover - optional dependency detection
    OPENTELEMETRY_AVAILABLE = False

logger = logging.getLogger(__name__)


class OpenTelemetryExporter(MetricExporter):
    """Send metrics to an OpenTelemetry collector using OTLP."""

    def __init__(
        self,
        name: str = "opentelemetry",
        service_name: str = "neuroca",
        endpoint: str = "http://localhost:4317",
        **kwargs: Any,
    ) -> None:
        """Create the exporter and verify OpenTelemetry dependencies."""
        super().__init__(name=name, **kwargs)

        if not OPENTELEMETRY_AVAILABLE:
            raise ConfigurationError(
                "OpenTelemetry libraries not available. "
                "Install with 'pip install opentelemetry-api opentelemetry-sdk "
                "opentelemetry-exporter-otlp-proto-grpc'"
            )

        self.service_name = service_name
        self.endpoint = endpoint
        self.meter_provider: Optional[MeterProvider] = None
        self.meter: Optional[Any] = None
        self.metrics_dict: Dict[Tuple[str, str], Any] = {}

        logger.info(
            "Created OpenTelemetry exporter for service '%s' to endpoint %s",
            service_name,
            endpoint,
        )

    def initialize(self) -> None:
        """Initialise the OpenTelemetry meter provider and exporter."""
        try:
            otlp_exporter = OTLPMetricExporter(endpoint=self.endpoint)
            reader = PeriodicExportingMetricReader(
                exporter=otlp_exporter,
                export_interval_millis=self.flush_interval * 1000,
            )
            self.meter_provider = MeterProvider(metric_readers=[reader])
            otel_metrics.set_meter_provider(self.meter_provider)
            self.meter = otel_metrics.get_meter(name=self.service_name, version="1.0.0")
            logger.info("Initialized OpenTelemetry exporter for service '%s'", self.service_name)
            self._initialized = True
        except Exception as exc:  # pragma: no cover - failure path
            logger.error("Failed to initialise OpenTelemetry exporter: %s", exc)
            raise ConfigurationError(
                f"Failed to initialise OpenTelemetry exporter: {exc}"
            ) from exc

    def _get_or_create_metric(self, name: str, metric_type: str) -> Any:
        """Return a cached or newly created OpenTelemetry metric."""
        metric_key = (name, metric_type)
        if metric_key in self.metrics_dict:
            return self.metrics_dict[metric_key]

        if self.meter is None:  # pragma: no cover - defensive guard
            raise ExportError("OpenTelemetry meter has not been initialised")

        description = f"{name} {metric_type}"
        metric = self._create_metric(name, metric_type, description)
        self.metrics_dict[metric_key] = metric
        return metric

    def _create_metric(self, name: str, metric_type: str, description: str) -> Any:
        """Create the correct metric implementation for the requested type."""
        assert self.meter is not None  # Defensive; handled above
        if metric_type == MetricType.COUNTER.value:
            return self.meter.create_counter(name=name, description=description, unit="1")
        if metric_type == MetricType.GAUGE.value:
            return self.meter.create_up_down_counter(name=name, description=description, unit="1")
        if metric_type == MetricType.HISTOGRAM.value:
            return self.meter.create_histogram(name=name, description=description, unit="1")
        logger.warning(
            "Unsupported metric type '%s' for OpenTelemetry, using counter", metric_type
        )
        return self.meter.create_counter(name=name, description=f"{name} counter", unit="1")

    def _export_batch(self, metrics: list[dict[str, Any]]) -> None:
        """Export a batch of metrics to OpenTelemetry."""
        try:
            for metric in metrics:
                otel_metric = self._get_or_create_metric(metric["name"], metric["type"])
                self._update_metric(otel_metric, metric)
            logger.debug("Exported %s metrics to OpenTelemetry", len(metrics))
        except Exception as exc:
            logger.error("Failed to export metrics to OpenTelemetry: %s", exc)
            raise ExportError(f"Failed to export metrics to OpenTelemetry: {exc}") from exc

    def _update_metric(self, otel_metric: Any, metric: dict[str, Any]) -> None:
        """Apply the metric update for the requested OpenTelemetry instrument."""
        metric_type = metric["type"]
        value = metric["value"]
        labels = metric["labels"]

        if metric_type == MetricType.COUNTER.value:
            otel_metric.add(value, labels)
        elif metric_type == MetricType.GAUGE.value:
            otel_metric.add(value, labels)
        elif metric_type == MetricType.HISTOGRAM.value:
            otel_metric.record(value, labels)
        else:
            otel_metric.add(value, labels)

    def close(self) -> None:
        """Shut down the OpenTelemetry meter provider."""
        try:
            super().close()
            if self.meter_provider:
                self.meter_provider.shutdown()
                logger.info("Shut down OpenTelemetry meter provider")
        except Exception as exc:  # pragma: no cover - shutdown best effort
            logger.error("Error shutting down OpenTelemetry exporter: %s", exc)
