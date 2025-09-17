"""Domain models describing agents and their capabilities."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(slots=True)
class AgentCapability:
    """Represents a capability the agent can exercise."""

    identifier: str
    name: str
    proficiency: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def normalised_proficiency(self) -> float:
        """Return a proficiency score clamped between 0 and 1."""

        return max(0.0, min(1.0, self.proficiency))


@dataclass(slots=True)
class AgentProfile:
    """Describes persistent traits for an agent."""

    identifier: str
    display_name: str
    description: str = ""
    preferences: Dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AgentState:
    """Captures the agent's momentary status."""

    identifier: str
    mood: str = "neutral"
    focus: float = 0.5
    active_goal: Optional[str] = None

    def adjust_focus(self, delta: float) -> None:
        """Adjust the focus level while keeping it within bounds."""

        self.focus = max(0.0, min(1.0, self.focus + delta))


@dataclass(slots=True)
class Agent:
    """Aggregate model combining profile, capabilities, and state."""

    identifier: str
    profile: AgentProfile
    capabilities: List[AgentCapability] = field(default_factory=list)
    state: AgentState = field(default_factory=lambda: AgentState(identifier="default"))

    def capability_map(self) -> Dict[str, AgentCapability]:
        """Return capabilities indexed by identifier for quick lookup."""

        return {capability.identifier: capability for capability in self.capabilities}

    def update_state(self, *, mood: Optional[str] = None, focus_delta: Optional[float] = None) -> None:
        """Convenience wrapper to update the active state."""

        if mood is not None:
            self.state.mood = mood
        if focus_delta is not None:
            self.state.adjust_focus(focus_delta)
