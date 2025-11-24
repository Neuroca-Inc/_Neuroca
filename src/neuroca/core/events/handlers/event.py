"""Core event data model for handler processing.

The :class:`Event` dataclass provides the canonical payload for the legacy
handler stack. It intentionally mirrors the historical implementation so that
existing event producers continue to work while the module is decomposed into
single-class files.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import uuid
from typing import Any, Optional


@dataclass
class Event:
    """Base event payload consumed by legacy handlers.

    Attributes:
        id: Stable identifier for the event instance. Auto-generated when
            omitted to preserve compatibility with stored references.
        timestamp: Creation timestamp recorded for auditing and ordering.
        source: Optional string identifier describing the event producer.
        metadata: Free-form metadata dictionary propagated to handlers.
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.now)
    source: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Normalise core fields after instantiation.

        The historical implementation accepted partially populated inputs and
        repaired them on the fly. The behaviour is maintained for backwards
        compatibility so call sites that rely on implicit defaults remain
        functional.
        """

        if not self.id:
            self.id = str(uuid.uuid4())
        if not isinstance(self.timestamp, datetime):
            self.timestamp = datetime.now()
        if not isinstance(self.metadata, dict):
            self.metadata = {}


__all__ = ["Event"]
