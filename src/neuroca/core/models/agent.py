"""Agent domain models used across the cognitive-control stack."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from .base import BaseModel, ValidationError
from .health import HealthMetrics
from .user import CognitiveProfile


class AgentCapability(BaseModel):
    """Describes a skill or tool available to an agent."""

    def __init__(
        self,
        *,
        name: str,
        description: str = "",
        proficiency: float = 0.0,
        metadata: Optional[Dict[str, Any]] = None,
        id: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(id=id, **kwargs)
        self.name = name
        self.description = description
        self.proficiency = float(proficiency)
        self.metadata = dict(metadata or {})

    def validate(self) -> None:
        super().validate()
        if not self.name:
            raise ValidationError("AgentCapability requires a name")
        if not 0.0 <= self.proficiency <= 1.0:
            raise ValidationError("proficiency must be between 0.0 and 1.0")


class AgentState(BaseModel):
    """Snapshot of current agent operating state."""

    def __init__(
        self,
        *,
        status: str = "idle",
        goal: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        updated_at: Optional[datetime] = None,
        id: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(id=id, **kwargs)
        self.status = status
        self.goal = goal
        self.context = dict(context or {})
        self.updated_at = updated_at or datetime.utcnow()

    def validate(self) -> None:
        super().validate()
        if not isinstance(self.status, str) or not self.status:
            raise ValidationError("status must be a non-empty string")


class AgentProfile(BaseModel):
    """Stable agent attributes and configuration."""

    def __init__(
        self,
        *,
        name: str,
        description: str = "",
        capabilities: Optional[list[AgentCapability]] = None,
        preferences: Optional[Dict[str, Any]] = None,
        id: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(id=id, **kwargs)
        self.name = name
        self.description = description
        self.capabilities = capabilities or []
        self.preferences = dict(preferences or {})

    def validate(self) -> None:
        super().validate()
        if not self.name:
            raise ValidationError("AgentProfile requires a name")
        for capability in self.capabilities:
            if isinstance(capability, AgentCapability):
                capability.validate()


class Agent(BaseModel):
    """Top-level agent record tying together profile and state."""

    def __init__(
        self,
        *,
        identifier: str,
        profile: AgentProfile | Dict[str, Any],
        state: AgentState | Dict[str, Any] | None = None,
        cognitive_profile: CognitiveProfile | Dict[str, Any] | None = None,
        health: HealthMetrics | Dict[str, Any] | None = None,
        metadata: Optional[Dict[str, Any]] = None,
        id: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(id=id or identifier, **kwargs)
        self.identifier = identifier
        self.profile = (
            profile
            if isinstance(profile, AgentProfile)
            else AgentProfile(**profile)
        )
        self.state = (
            state
            if isinstance(state, AgentState)
            else AgentState(**state)
            if state
            else AgentState(status="idle")
        )
        self.cognitive_profile = (
            cognitive_profile
            if isinstance(cognitive_profile, CognitiveProfile)
            else CognitiveProfile(**cognitive_profile)
            if cognitive_profile
            else CognitiveProfile()
        )
        self.health = (
            health
            if isinstance(health, HealthMetrics)
            else HealthMetrics(**health)
            if health
            else HealthMetrics()
        )
        self.metadata = dict(metadata or {})

    def validate(self) -> None:
        super().validate()
        if not self.identifier:
            raise ValidationError("Agent requires an identifier")
        self.profile.validate()
        self.state.validate()
        self.cognitive_profile.validate()
        self.health.validate()


__all__ = [
    "Agent",
    "AgentProfile",
    "AgentCapability",
    "AgentState",
]

