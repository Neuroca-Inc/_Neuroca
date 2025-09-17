"""User and profile domain models for the Neuroca platform."""

from __future__ import annotations

import hashlib
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from .base import BaseModel, ValidationError
from .health import HealthMetrics


class UserRole(str, Enum):
    """Supported roles for platform users."""

    USER = "user"
    ADMIN = "admin"
    ANALYST = "analyst"
    SYSTEM = "system"


class UserPreferences(BaseModel):
    """UI and experience preferences associated with a user."""

    def __init__(
        self,
        *,
        theme: str = "light",
        notifications_enabled: bool = True,
        timezone: str = "UTC",
        language: str = "en",
        session_timeout_minutes: int = 30,
        accessibility_mode: bool = False,
        custom_settings: Optional[Dict[str, Any]] = None,
        id: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(id=id, **kwargs)
        self.theme = theme
        self.notifications_enabled = notifications_enabled
        self.timezone = timezone
        self.language = language
        self.session_timeout_minutes = session_timeout_minutes
        self.accessibility_mode = accessibility_mode
        self.custom_settings: Dict[str, Any] = dict(custom_settings or {})

    def validate(self) -> None:
        super().validate()
        if self.session_timeout_minutes <= 0:
            raise ValidationError("session_timeout_minutes must be positive")


class CognitiveProfile(BaseModel):
    """High level cognitive capabilities captured for a user."""

    def __init__(
        self,
        *,
        attention_span: int = 50,
        memory_capacity: int = 50,
        learning_rate: int = 50,
        reasoning_ability: int = 50,
        creativity: int = 50,
        adaptability: int = 50,
        processing_speed: int = 50,
        traits: Optional[Dict[str, int]] = None,
        id: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(id=id, **kwargs)
        self.attention_span = attention_span
        self.memory_capacity = memory_capacity
        self.learning_rate = learning_rate
        self.reasoning_ability = reasoning_ability
        self.creativity = creativity
        self.adaptability = adaptability
        self.processing_speed = processing_speed
        self.traits: Dict[str, int] = dict(traits or {})

    def validate(self) -> None:
        super().validate()
        for attribute in (
            "attention_span",
            "memory_capacity",
            "learning_rate",
            "reasoning_ability",
            "creativity",
            "adaptability",
            "processing_speed",
        ):
            value = getattr(self, attribute)
            if not 0 <= value <= 100:
                raise ValidationError(f"{attribute} must be between 0 and 100")


class User(BaseModel):
    """Core representation of an authenticated platform user."""

    def __init__(
        self,
        *,
        username: str,
        email: str,
        password_hash: Optional[str] = None,
        first_name: str = "",
        last_name: str = "",
        role: UserRole | str = UserRole.USER,
        is_active: bool = True,
        created_at: Optional[datetime] = None,
        last_login: Optional[datetime] = None,
        preferences: UserPreferences | Dict[str, Any] | None = None,
        cognitive_profile: CognitiveProfile | Dict[str, Any] | None = None,
        health_metrics: HealthMetrics | Dict[str, Any] | None = None,
        tags: Optional[list[str]] = None,
        id: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(id=id, **kwargs)
        self.username = username
        self.email = email
        self.password_hash = password_hash or self.hash_password(username)
        self.first_name = first_name
        self.last_name = last_name
        self.role = UserRole(role) if not isinstance(role, UserRole) else role
        self.is_active = is_active
        self.created_at = created_at or datetime.utcnow()
        self.last_login = last_login
        self.preferences = (
            preferences
            if isinstance(preferences, UserPreferences)
            else UserPreferences(**preferences)
            if preferences
            else UserPreferences()
        )
        self.cognitive_profile = (
            cognitive_profile
            if isinstance(cognitive_profile, CognitiveProfile)
            else CognitiveProfile(**cognitive_profile)
            if cognitive_profile
            else CognitiveProfile()
        )
        self.health_metrics = (
            health_metrics
            if isinstance(health_metrics, HealthMetrics)
            else HealthMetrics(**health_metrics)
            if health_metrics
            else HealthMetrics()
        )
        self.tags = list(tags or [])

    @staticmethod
    def hash_password(password: str) -> str:
        """Create a deterministic hash for the provided password."""

        digest = hashlib.sha256()
        digest.update(password.encode("utf-8"))
        return digest.hexdigest()

    def validate(self) -> None:
        super().validate()
        if not self.username:
            raise ValidationError("username must be provided")
        if "@" not in self.email:
            raise ValidationError("email must contain '@'")
        if not isinstance(self.tags, list):
            raise ValidationError("tags must be a list")
        self.preferences.validate()
        self.cognitive_profile.validate()
        self.health_metrics.validate()

    def set_password(self, password: str) -> None:
        """Assign a new password hash."""

        self.password_hash = self.hash_password(password)

    def check_password(self, password: str) -> bool:
        """Verify that the provided password matches the stored hash."""

        return self.password_hash == self.hash_password(password)


__all__ = [
    "UserRole",
    "UserPreferences",
    "CognitiveProfile",
    "User",
]

