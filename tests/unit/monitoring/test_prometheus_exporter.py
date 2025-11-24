"""Tests covering the Prometheus metrics exporter HTTP endpoint handling."""

from __future__ import annotations

import time
from urllib.error import HTTPError
from urllib.request import urlopen

import pytest

from neuroca.monitoring.metrics.exporters import MetricType, PrometheusExporter


def _read_metrics(url: str) -> str:
    """Fetch and decode the metrics payload from the given URL."""

    with urlopen(url) as response:  # nosec: B310 - local test harness
        return response.read().decode("utf-8")


def test_prometheus_exporter_serves_default_endpoint() -> None:
    """Ensure the exporter publishes metrics on the default ``/metrics`` route."""

    exporter = PrometheusExporter(name="test-default", port=0, host="127.0.0.1")
    try:
        exporter.export_metric(
            "memory_manager_test_metric",
            1.0,
            labels={"tier": "stm"},
            metric_type=MetricType.GAUGE,
        )
        exporter.flush()
        time.sleep(0.1)

        payload = _read_metrics(f"http://127.0.0.1:{exporter.port}/metrics")
        assert "memory_manager_test_metric" in payload
    finally:
        exporter.close()


def test_prometheus_exporter_custom_endpoint() -> None:
    """Validate that a custom endpoint returns metrics and the default path 404s."""

    exporter = PrometheusExporter(
        name="test-custom",
        port=0,
        host="127.0.0.1",
        endpoint="/custom-metrics",
    )
    try:
        exporter.export_metric(
            "custom_memory_metric",
            42.0,
            labels={},
            metric_type=MetricType.GAUGE,
        )
        exporter.flush()
        time.sleep(0.1)

        payload = _read_metrics(f"http://127.0.0.1:{exporter.port}/custom-metrics")
        assert "custom_memory_metric" in payload

        with pytest.raises(HTTPError):
            _read_metrics(f"http://127.0.0.1:{exporter.port}/metrics")
    finally:
        exporter.close()
