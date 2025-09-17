"""Domain models capturing health metrics for the system."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass(slots=True)
class HealthMetrics:
    """Aggregated health metrics for a component."""

    identifier: str
    energy_level: float = 1.0
    stress_level: float = 0.0
    additional_metrics: Dict[str, float] = field(default_factory=dict)

    def clamp(self) -> None:
        """Clamp primary metrics to sensible ranges."""

        self.energy_level = max(0.0, min(1.0, self.energy_level))
        self.stress_level = max(0.0, min(1.0, self.stress_level))


@dataclass(slots=True)
class ResourceUtilization:
    """Tracks how system resources are being utilised."""

    identifier: str
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    notes: Dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class PerformanceIndicators:
    """High-level performance indicators used by monitoring routines."""

    identifier: str
    throughput: float = 0.0
    latency: float = 0.0
    reliability: float = 1.0


@dataclass(slots=True)
class SystemState:
    """Represents the overall health state of the system."""

    identifier: str
    metrics: HealthMetrics
    utilisation: ResourceUtilization
    performance: PerformanceIndicators

    def summarise(self) -> Dict[str, Any]:
        """Provide a dictionary summary suitable for logging or serialisation."""

        return {
            "identifier": self.identifier,
            "energy": self.metrics.energy_level,
            "stress": self.metrics.stress_level,
            "cpu": self.utilisation.cpu_usage,
            "memory": self.utilisation.memory_usage,
            "throughput": self.performance.throughput,
            "latency": self.performance.latency,
            "reliability": self.performance.reliability,
        }
