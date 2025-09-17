"""Domain objects describing cognitive processes and attention."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from neuroca.core.enums import CognitiveState
from neuroca.memory.models import WorkingMemoryBuffer

from .base import BaseModel, ValidationError


class CognitiveProcess(BaseModel):
    """Represents a long running cognitive activity."""

    def __init__(
        self,
        *,
        name: str,
        state: CognitiveState | str = CognitiveState.IDLE,
        last_transition: Optional[datetime] = None,
        metadata: Optional[dict[str, Any]] = None,
        id: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(id=id, **kwargs)
        self.name = name
        self.state = CognitiveState(state) if not isinstance(state, CognitiveState) else state
        self.last_transition = last_transition or datetime.utcnow()
        self.metadata = dict(metadata or {})

    def validate(self) -> None:
        super().validate()
        if not self.name:
            raise ValidationError("CognitiveProcess requires a name")


class Attention(BaseModel):
    """Attention focus across multiple targets."""

    def __init__(
        self,
        *,
        focus_level: float = 0.5,
        distraction_level: float = 0.0,
        target: Optional[str] = None,
        buffer: Optional[WorkingMemoryBuffer] = None,
        id: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(id=id, **kwargs)
        self.focus_level = float(focus_level)
        self.distraction_level = float(distraction_level)
        self.target = target
        self.buffer = buffer or WorkingMemoryBuffer()

    def validate(self) -> None:
        super().validate()
        for attr in ("focus_level", "distraction_level"):
            value = getattr(self, attr)
            if not 0.0 <= value <= 1.0:
                raise ValidationError(f"{attr} must be between 0.0 and 1.0")


__all__ = [
    "CognitiveProcess",
    "Attention",
    "WorkingMemoryBuffer",
    "CognitiveState",
]

