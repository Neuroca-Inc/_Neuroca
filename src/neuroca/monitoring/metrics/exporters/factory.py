"""Factory helpers for constructing metrics exporters from configuration."""

from __future__ import annotations

import logging
from typing import Any, Dict, Iterable

from .base import MetricExporter
from .composite import CompositeExporter
from .configuration_error import ConfigurationError
from .json_file import JsonFileExporter
from .logging_exporter import LoggingExporter
from .opentelemetry import OpenTelemetryExporter
from .prometheus import PrometheusExporter

__all__ = ["create_exporter"]


def create_exporter(config: Dict[str, Any]) -> MetricExporter:
    """Instantiate a configured exporter from a mapping."""
    exporter_type = str(config.get("type", "")).strip().lower()
    if not exporter_type:
        raise ConfigurationError("Exporter type not specified in configuration")

    name = str(config.get("name", exporter_type))
    batch_size = int(config.get("batch_size", 100))
    flush_interval = int(config.get("flush_interval", 60))

    if exporter_type == "prometheus":
        return PrometheusExporter(
            name=name,
            endpoint=str(config.get("endpoint", "/metrics")),
            port=int(config.get("port", 9090)),
            host=str(config.get("host", "0.0.0.0")),
            batch_size=batch_size,
            flush_interval=flush_interval,
        )
    if exporter_type == "opentelemetry":
        return OpenTelemetryExporter(
            name=name,
            service_name=str(config.get("service_name", "neuroca")),
            endpoint=str(config.get("endpoint", "http://localhost:4317")),
            batch_size=batch_size,
            flush_interval=flush_interval,
        )
    if exporter_type == "logging":
        return LoggingExporter(
            name=name,
            logger_name=config.get("logger_name"),
            log_level=_coerce_log_level(config.get("log_level", logging.INFO)),
            batch_size=batch_size,
            flush_interval=flush_interval,
        )
    if exporter_type == "json_file":
        return JsonFileExporter(
            name=name,
            file_path=str(config.get("file_path", "metrics.json")),
            append=bool(config.get("append", True)),
            batch_size=batch_size,
            flush_interval=flush_interval,
        )
    if exporter_type == "composite":
        sub_configs = config.get("exporters", [])
        sub_exporters = _create_sub_exporters(sub_configs)
        return CompositeExporter(
            name=name,
            exporters=sub_exporters,
            batch_size=batch_size,
            flush_interval=flush_interval,
        )

    raise ConfigurationError(f"Unknown exporter type: {exporter_type}")


def _create_sub_exporters(configs: Iterable[Dict[str, Any]]) -> list[MetricExporter]:
    """Recursively create exporters defined inside a composite configuration."""
    exporters: list[MetricExporter] = []
    for sub_config in configs:
        exporters.append(create_exporter(sub_config))
    return exporters


def _coerce_log_level(value: Any) -> int:
    """Translate configuration values into valid logging levels."""
    if isinstance(value, int):
        return value

    if isinstance(value, str):
        level = logging.getLevelName(value.upper())
        if isinstance(level, int):
            return level

    raise ConfigurationError(f"Invalid logging level: {value}")
