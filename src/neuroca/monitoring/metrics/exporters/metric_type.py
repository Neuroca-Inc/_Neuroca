"""Enumerations describing the metric kinds exporters can emit."""

from __future__ import annotations

from enum import Enum

__all__ = ["MetricType"]


class MetricType(Enum):
    """Enumeration of supported metric types for metrics exporters."""

    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"
