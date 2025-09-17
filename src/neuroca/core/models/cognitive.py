"""Domain models representing cognitive constructs."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass(slots=True)
class CognitiveState:
    """Snapshot of a cognitive state with activation and context."""

    identifier: str
    activation: float = 0.5
    context: Dict[str, Any] = field(default_factory=dict)

    def clamp_activation(self) -> None:
        """Ensure the activation level is within [0, 1]."""

        self.activation = max(0.0, min(1.0, self.activation))


@dataclass(slots=True)
class CognitiveProcess:
    """Represents an ongoing cognitive process."""

    identifier: str
    name: str
    state: CognitiveState
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Attention:
    """Simple model for attention allocation."""

    identifier: str
    focus: float = 0.5
    distribution: Dict[str, float] = field(default_factory=dict)

    def normalise(self) -> None:
        """Normalise the distribution so that weights sum to one."""

        total = sum(self.distribution.values())
        if not total:
            return
        for key, value in list(self.distribution.items()):
            self.distribution[key] = value / total


@dataclass(slots=True)
class WorkingMemoryBuffer:
    """Represents a lightweight working-memory buffer."""

    identifier: str
    capacity: int = 5
    items: List[str] = field(default_factory=list)

    def add(self, item: str) -> None:
        """Insert an item while enforcing the capacity limit."""

        self.items.append(item)
        if len(self.items) > self.capacity:
            self.items.pop(0)
