"""Pydantic-lite models representing metrics payloads for APIs."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional

from .base import BaseModel, ValidationError
from .health import HealthMetrics, PerformanceIndicators, ResourceUtilization, SystemState


class MetricType(str, Enum):
    """Categorisation of supported metric families."""

    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


class MetricDefinition(BaseModel):
    """Static definition describing an available metric."""

    def __init__(
        self,
        *,
        name: str,
        description: str,
        type: MetricType | str,
        unit: str,
        aggregation: str = "last",
        retention_days: int = 30,
        labels: Optional[List[str]] = None,
        id: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(id=id or name, **kwargs)
        self.name = name
        self.description = description
        self.type = type if isinstance(type, MetricType) else MetricType(type)
        self.unit = unit
        self.aggregation = aggregation
        self.retention_days = retention_days
        self.labels = list(labels or [])

    def validate(self) -> None:
        super().validate()
        if not self.name:
            raise ValidationError("MetricDefinition requires a name")
        if self.retention_days <= 0:
            raise ValidationError("retention_days must be positive")


class MetricSummary(BaseModel):
    """Aggregated view of a metric across a time window."""

    def __init__(
        self,
        *,
        name: str,
        unit: str,
        count: int,
        total: float,
        minimum: float,
        maximum: float,
        average: float,
        latest: float,
        id: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(id=id or name, **kwargs)
        self.name = name
        self.unit = unit
        self.count = count
        self.total = float(total)
        self.minimum = float(minimum)
        self.maximum = float(maximum)
        self.average = float(average)
        self.latest = float(latest)

    def validate(self) -> None:
        super().validate()
        if self.count < 0:
            raise ValidationError("count cannot be negative")


class MetricTimeseriesData(BaseModel):
    """Discrete data points representing historical metric values."""

    def __init__(
        self,
        *,
        name: str,
        unit: str,
        points: Iterable[tuple[datetime, float] | Dict[str, Any]],
        id: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(id=id or name, **kwargs)
        processed: list[dict[str, Any]] = []
        for point in points:
            if isinstance(point, dict):
                timestamp = point.get("timestamp")
                value = point.get("value")
            else:
                timestamp, value = point
            processed.append({
                "timestamp": timestamp if isinstance(timestamp, datetime) else datetime.fromisoformat(str(timestamp)),
                "value": float(value),
            })
        self.name = name
        self.unit = unit
        self.points = processed


class MemoryMetrics(BaseModel):
    """Metrics returned by the memory monitoring API."""

    def __init__(
        self,
        *,
        tier: str,
        total_items: int,
        retrieval_latency_ms: float,
        hit_rate: float,
        utilization: ResourceUtilization | Dict[str, Any],
        id: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(id=id or tier, **kwargs)
        self.tier = tier
        self.total_items = total_items
        self.retrieval_latency_ms = float(retrieval_latency_ms)
        self.hit_rate = float(hit_rate)
        self.utilization = (
            utilization
            if isinstance(utilization, ResourceUtilization)
            else ResourceUtilization(**utilization)
        )


class PerformanceMetrics(BaseModel):
    """System performance characteristics."""

    def __init__(
        self,
        *,
        component: Optional[str],
        indicators: PerformanceIndicators | Dict[str, Any],
        timeframe: str,
        id: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(id=id or component or "global", **kwargs)
        self.component = component
        self.indicators = (
            indicators
            if isinstance(indicators, PerformanceIndicators)
            else PerformanceIndicators(**indicators)
        )
        self.timeframe = timeframe


class SystemHealthMetrics(BaseModel):
    """Top-level health metrics returned to monitoring dashboards."""

    def __init__(
        self,
        *,
        state: SystemState | Dict[str, Any],
        components: List[HealthMetrics | Dict[str, Any]],
        generated_at: Optional[datetime] = None,
        id: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(id=id or "system-health", **kwargs)
        self.state = state if isinstance(state, SystemState) else SystemState(**state)
        self.components = [
            metric if isinstance(metric, HealthMetrics) else HealthMetrics(**metric)
            for metric in components
        ]
        self.generated_at = generated_at or datetime.utcnow()


__all__ = [
    "MetricType",
    "MetricDefinition",
    "MetricSummary",
    "MetricTimeseriesData",
    "MemoryMetrics",
    "PerformanceMetrics",
    "SystemHealthMetrics",
]

