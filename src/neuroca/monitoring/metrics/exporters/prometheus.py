"""Prometheus exporter implementation used by the monitoring subsystem."""

from __future__ import annotations

import logging
import threading
from typing import Any, Callable, Dict, Optional, Tuple
from wsgiref.simple_server import WSGIRequestHandler, make_server

from .configuration_error import ConfigurationError
from .export_error import ExportError
from .metric_type import MetricType
from .threaded_wsgi_server import ThreadedWSGIServer
from .base import MetricExporter

__all__ = ["PROMETHEUS_AVAILABLE", "PrometheusExporter"]

try:  # pragma: no cover - optional dependency detection
    import prometheus_client

    PROMETHEUS_AVAILABLE = True
except ImportError:  # pragma: no cover - optional dependency detection
    PROMETHEUS_AVAILABLE = False

logger = logging.getLogger(__name__)


class PrometheusExporter(MetricExporter):
    """Expose in-process metrics through a Prometheus scrape endpoint."""

    def __init__(
        self,
        name: str = "prometheus",
        endpoint: str = "/metrics",
        port: int = 9090,
        host: str = "0.0.0.0",
        **kwargs: Any,
    ) -> None:
        """Create the exporter and validate the Prometheus dependency."""
        super().__init__(name=name, **kwargs)

        if not PROMETHEUS_AVAILABLE:
            raise ConfigurationError(
                "Prometheus client library not available. "
                "Install with 'pip install prometheus-client'"
            )

        self.endpoint = self._normalise_endpoint(endpoint)
        self.host = host
        self.port = port
        self.registry: Optional[prometheus_client.CollectorRegistry] = None
        self.metrics_dict: Dict[Tuple[str, str, Tuple[str, ...]], Any] = {}
        self._server: Optional[ThreadedWSGIServer] = None
        self._server_thread: Optional[threading.Thread] = None

        logger.info("Created Prometheus exporter on %s:%s at %s", host, port, self.endpoint)

    def initialize(self) -> None:
        """Initialise the Prometheus HTTP server and backing registry."""
        try:
            self.registry = prometheus_client.CollectorRegistry()
            application = prometheus_client.make_wsgi_app(self.registry)
            wrapped_application = self._wrap_app_with_endpoint(application, self.endpoint)

            self._server = make_server(
                self.host,
                self.port,
                wrapped_application,
                server_class=ThreadedWSGIServer,
                handler_class=WSGIRequestHandler,
            )
            self.port = self._server.server_port
            self._server_thread = threading.Thread(
                target=self._server.serve_forever,
                name=f"{self.name}-prometheus-server",
                daemon=True,
            )
            self._server_thread.start()
            logger.info(
                "Started Prometheus HTTP server on %s:%s at %s",
                self.host,
                self.port,
                self.endpoint,
            )
            self._initialized = True
        except Exception as exc:  # pragma: no cover - failure path
            logger.error("Failed to initialise Prometheus exporter: %s", exc)
            raise ConfigurationError(
                f"Failed to initialise Prometheus exporter: {exc}"
            ) from exc

    def _get_or_create_metric(
        self,
        name: str,
        metric_type: str,
        labels: Dict[str, str],
    ) -> Tuple[Any, Tuple[str, ...]]:
        """Return the Prometheus metric and label order for the provided payload."""
        if self.registry is None:  # pragma: no cover - defensive guard
            raise ExportError("Prometheus registry has not been initialised")

        label_names = tuple(sorted(labels.keys()))
        metric_key = (name, metric_type, label_names)

        if metric_key not in self.metrics_dict:
            self.metrics_dict[metric_key] = self._create_metric(name, metric_type, label_names)

        label_values = tuple(labels.get(label, "") for label in label_names)
        return self.metrics_dict[metric_key], label_values

    def _create_metric(
        self,
        name: str,
        metric_type: str,
        label_names: Tuple[str, ...],
    ) -> Any:
        """Construct a Prometheus metric for the requested type."""
        if metric_type == MetricType.COUNTER.value:
            return prometheus_client.Counter(name, f"{name} counter", label_names, registry=self.registry)
        if metric_type == MetricType.GAUGE.value:
            return prometheus_client.Gauge(name, f"{name} gauge", label_names, registry=self.registry)
        if metric_type == MetricType.HISTOGRAM.value:
            return prometheus_client.Histogram(name, f"{name} histogram", label_names, registry=self.registry)
        if metric_type == MetricType.SUMMARY.value:
            return prometheus_client.Summary(name, f"{name} summary", label_names, registry=self.registry)
        raise ValueError(f"Unsupported metric type: {metric_type}")

    def _export_batch(self, metrics: list[dict[str, Any]]) -> None:
        """Export a batch of metrics to Prometheus."""
        try:
            for metric in metrics:
                prometheus_metric, label_values = self._get_or_create_metric(
                    metric["name"],
                    metric["type"],
                    metric["labels"],
                )
                self._update_metric(metric, prometheus_metric, label_values)

            logger.debug("Exported %s metrics to Prometheus", len(metrics))
        except Exception as exc:
            logger.error("Failed to export metrics to Prometheus: %s", exc)
            raise ExportError(f"Failed to export metrics to Prometheus: {exc}") from exc

    def _update_metric(self, metric: dict[str, Any], prometheus_metric: Any, label_values: Tuple[str, ...]) -> None:
        """Apply a metric value update based on the metric type."""
        metric_type = metric["type"]
        value = metric["value"]

        if metric_type == MetricType.COUNTER.value:
            self._increment_counter(prometheus_metric, label_values, value)
        elif metric_type == MetricType.GAUGE.value:
            self._set_gauge(prometheus_metric, label_values, value)
        else:
            self._observe_sample(prometheus_metric, label_values, value)

    def _increment_counter(self, prometheus_metric: Any, label_values: Tuple[str, ...], value: float) -> None:
        """Increment a Prometheus counter with optional labels."""
        if label_values:
            prometheus_metric.labels(*label_values).inc(value)
        else:
            prometheus_metric.inc(value)

    def _set_gauge(self, prometheus_metric: Any, label_values: Tuple[str, ...], value: float) -> None:
        """Set a Prometheus gauge with optional labels."""
        if label_values:
            prometheus_metric.labels(*label_values).set(value)
        else:
            prometheus_metric.set(value)

    def _observe_sample(self, prometheus_metric: Any, label_values: Tuple[str, ...], value: float) -> None:
        """Record a sample for histogram or summary metrics."""
        if label_values:
            prometheus_metric.labels(*label_values).observe(value)
        else:
            prometheus_metric.observe(value)

    def close(self) -> None:
        """Stop the HTTP server before performing the base shutdown."""
        try:
            if self._server is not None:
                self._server.shutdown()
                self._server.server_close()
                if self._server_thread is not None and self._server_thread.is_alive():
                    self._server_thread.join(timeout=1.0)
        finally:
            self._server = None
            self._server_thread = None

        super().close()

    @staticmethod
    def _normalise_endpoint(endpoint: str) -> str:
        """Return a scrape endpoint that always begins with ``/``."""
        if not endpoint:
            return "/metrics"

        cleaned = endpoint.strip() or "/metrics"
        if not cleaned.startswith("/"):
            cleaned = f"/{cleaned}"
        return cleaned

    @staticmethod
    def _wrap_app_with_endpoint(
        application: Callable[[dict[str, Any], Callable[..., Any]], Any],
        endpoint: str,
    ) -> Callable[[dict[str, Any], Callable[..., Any]], Any]:
        """Wrap the Prometheus WSGI application to respect the configured endpoint."""
        normalised = endpoint or "/metrics"
        if normalised in {"/", ""}:
            return application

        def _wrapped(environ: dict[str, Any], start_response: Callable[..., Any]) -> Any:
            path = environ.get("PATH_INFO", "")
            if path == normalised:
                environ = dict(environ)
                environ["PATH_INFO"] = "/"
                return application(environ, start_response)

            start_response(
                "404 Not Found",
                [("Content-Type", "text/plain; charset=utf-8")],
            )
            return [b"Not Found"]

        return _wrapped
