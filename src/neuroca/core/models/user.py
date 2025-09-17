"""Domain models describing users interacting with the system."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass(slots=True)
class UserPreferences:
    """Lightweight structure for user-specific preferences."""

    identifier: str
    settings: Dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class UserProfile:
    """Represents a user's profile within the system."""

    identifier: str
    display_name: str
    email: str
    preferences: UserPreferences = field(default_factory=lambda: UserPreferences(identifier="default"))


@dataclass(slots=True)
class User:
    """Aggregate root capturing user profile and assigned roles."""

    identifier: str
    profile: UserProfile
    roles: List[str] = field(default_factory=list)
    is_active: bool = True

    def assign_role(self, role: str) -> None:
        """Assign a new role if not already present."""

        if role not in self.roles:
            self.roles.append(role)
