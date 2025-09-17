"""Compatibility wrapper re-exporting user domain models."""

from .user import CognitiveProfile, User, UserPreferences, UserRole

__all__ = [
    "User",
    "UserPreferences",
    "UserRole",
    "CognitiveProfile",
]

