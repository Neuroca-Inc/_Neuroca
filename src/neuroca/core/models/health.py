"""Domain models representing system health information for Neuroca."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Iterable, Optional

from .base import BaseModel, ValidationError

_DEFAULT_RANGE = (0.0, 100.0)


class HealthMetrics(BaseModel):
    """Aggregate health metrics for an agent or system component."""

    _VALUE_FIELDS: tuple[str, ...] = (
        "energy_level",
        "stress_level",
        "fatigue",
    )

    def __init__(
        self,
        *,
        energy_level: float = 100.0,
        stress_level: float = 0.0,
        fatigue: float = 0.0,
        metrics: Optional[Dict[str, float]] = None,
        last_updated: Optional[datetime] = None,
        id: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(id=id, **kwargs)
        self.energy_level = float(energy_level)
        self.stress_level = float(stress_level)
        self.fatigue = float(fatigue)
        self.metrics: Dict[str, float] = dict(metrics or {})
        self.last_updated = last_updated or datetime.utcnow()

    def validate(self) -> None:
        super().validate()
        for field_name in self._VALUE_FIELDS:
            value = getattr(self, field_name)
            if not _DEFAULT_RANGE[0] <= value <= _DEFAULT_RANGE[1]:
                raise ValidationError(
                    f"{field_name} must be within {_DEFAULT_RANGE}, received {value}"
                )

    def update_metric(self, name: str, value: float) -> None:
        """Set or update a dynamic metric value."""

        if not isinstance(name, str) or not name:
            raise ValidationError("Metric name must be a non-empty string")
        if not isinstance(value, (int, float)):
            raise ValidationError("Metric value must be numeric")
        self.metrics[name] = float(value)
        self.last_updated = datetime.utcnow()

    def update_from(self, updates: Dict[str, float] | Iterable[tuple[str, float]]) -> None:
        """Bulk update metrics from a mapping or iterable of pairs."""

        if isinstance(updates, dict):
            items = updates.items()
        else:
            items = updates
        for key, value in items:
            self.update_metric(key, value)


class ResourceUtilization(BaseModel):
    """Resource usage snapshot expressed as percentages."""

    def __init__(
        self,
        *,
        cpu: float = 0.0,
        memory: float = 0.0,
        disk: float = 0.0,
        network: float = 0.0,
        id: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(id=id, **kwargs)
        self.cpu = float(cpu)
        self.memory = float(memory)
        self.disk = float(disk)
        self.network = float(network)

    def validate(self) -> None:
        super().validate()
        for field_name in ("cpu", "memory", "disk", "network"):
            value = getattr(self, field_name)
            if not 0.0 <= value <= 1.0:
                raise ValidationError(
                    f"{field_name} utilisation must be between 0.0 and 1.0, received {value}"
                )


class PerformanceIndicators(BaseModel):
    """Performance characteristics collected for reporting."""

    def __init__(
        self,
        *,
        throughput: float = 0.0,
        latency_ms: float = 0.0,
        error_rate: float = 0.0,
        success_rate: float = 1.0,
        id: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(id=id, **kwargs)
        self.throughput = float(throughput)
        self.latency_ms = float(latency_ms)
        self.error_rate = float(error_rate)
        self.success_rate = float(success_rate)

    def validate(self) -> None:
        super().validate()
        if self.error_rate < 0.0:
            raise ValidationError("error_rate cannot be negative")
        if not 0.0 <= self.success_rate <= 1.0:
            raise ValidationError("success_rate must be between 0.0 and 1.0")


class SystemState(BaseModel):
    """Aggregated snapshot describing current system condition."""

    def __init__(
        self,
        *,
        status: str = "normal",
        summary: Optional[str] = None,
        energy_level: float = 100.0,
        stress_level: float = 0.0,
        updated_at: Optional[datetime] = None,
        utilization: Optional[ResourceUtilization | Dict[str, float]] = None,
        performance: Optional[PerformanceIndicators | Dict[str, float]] = None,
        id: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(id=id, **kwargs)
        self.status = status
        self.summary = summary or ""
        self.energy_level = float(energy_level)
        self.stress_level = float(stress_level)
        self.updated_at = updated_at or datetime.utcnow()
        self.utilization = (
            utilization
            if isinstance(utilization, ResourceUtilization)
            else ResourceUtilization(**utilization) if utilization else None
        )
        self.performance = (
            performance
            if isinstance(performance, PerformanceIndicators)
            else PerformanceIndicators(**performance) if performance else None
        )

    def validate(self) -> None:
        super().validate()
        if not isinstance(self.status, str) or not self.status:
            raise ValidationError("status must be a non-empty string")
        if not _DEFAULT_RANGE[0] <= self.energy_level <= _DEFAULT_RANGE[1]:
            raise ValidationError("energy_level out of expected range")
        if not _DEFAULT_RANGE[0] <= self.stress_level <= _DEFAULT_RANGE[1]:
            raise ValidationError("stress_level out of expected range")
        if self.utilization:
            self.utilization.validate()
        if self.performance:
            self.performance.validate()

