"""Domain models representing metrics tracked by the platform."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass(slots=True)
class MetricDefinition:
    """Defines a metric that can be collected and reported."""

    identifier: str
    metric_type: str
    description: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class MetricValue:
    """Holds a single observed value for a metric."""

    definition: MetricDefinition
    value: float
    unit: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class MetricSeries:
    """Collection of metric values captured over time."""

    identifier: str
    values: list[MetricValue] = field(default_factory=list)

    def average(self) -> Optional[float]:
        """Return the arithmetic mean of captured values if available."""

        if not self.values:
            return None
        return sum(entry.value for entry in self.values) / len(self.values)
