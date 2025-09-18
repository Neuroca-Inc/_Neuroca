"""Lightweight base event primitives used by memory event helpers."""

from __future__ import annotations

import enum
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict


class EventType(str, enum.Enum):
    """Enumeration describing coarse event categories."""

    MEMORY = "memory"
    SYSTEM = "system"
    UNKNOWN = "unknown"


class EventPriority(enum.IntEnum):
    """Priority levels for published events."""

    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3


@dataclass(kw_only=True)
class BaseEvent:
    """Base dataclass providing common event fields."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()), init=False)
    timestamp: datetime = field(default_factory=datetime.utcnow, init=False)
    source: str | None = field(default=None, init=False)
    metadata: Dict[str, Any] = field(default_factory=dict, init=False)
    event_type: EventType = field(default=EventType.UNKNOWN, init=False)
    priority: EventPriority = field(default=EventPriority.NORMAL, init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.timestamp, datetime):
            self.timestamp = datetime.utcnow()
        if not isinstance(self.metadata, dict):
            self.metadata = {}


__all__ = ["BaseEvent", "EventPriority", "EventType"]

