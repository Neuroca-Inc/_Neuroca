"""Typed retrieval result models for the legacy memory facade.

This module defines the concrete :class:`MemoryRetrievalResult` data structure
that the higher-level integrations depend on when interacting with the
``neuroca.memory`` package.  Earlier iterations exposed a lightweight stub that
offered little more than ``item`` and ``relevance`` attributes which made it
impossible to surface tier information, timestamps, or additional metadata in a
structured fashion.  The implementation provided here wraps the existing
``MemoryItem`` Pydantic model so consumers can reliably access rich memory
payloads without having to understand the internals of the tiered memory
manager.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from neuroca.memory.models.memory_item import MemoryItem


class MemoryRetrievalResult(BaseModel):
    """Container describing the outcome of a retrieval operation.

    Attributes:
        memory: Canonical representation of the retrieved item.
        tier: Memory tier that produced the result (``"working"``, ``"episodic"``
            or ``"semantic"``).
        relevance_score: Normalised score in the range ``0.0``–``1.0`` used for
            ordering results.
        metadata: Additional contextual information supplied by the underlying
            tier implementation.
        retrieved_at: Timestamp indicating when the retrieval occurred.
        summary: Optional short description supplied by the tier.
        similarity: Optional similarity score returned by vector enabled tiers.
    """

    memory: MemoryItem = Field(..., description="Canonical memory payload")
    tier: str = Field(..., description="Tier identifier that produced the result")
    relevance_score: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Normalised relevance score used for ranking",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional context emitted by the tier",
    )
    retrieved_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Timestamp describing when the retrieval happened",
    )
    summary: Optional[str] = Field(
        default=None,
        description="Optional natural language summary of the memory",
    )
    similarity: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Optional cosine similarity when available",
    )

    @property
    def memory_id(self) -> str:
        """Return the identifier of the wrapped memory item."""

        return self.memory.id

    @property
    def content(self) -> Dict[str, Any]:
        """Return the structured content of the memory item."""

        if isinstance(self.memory.content, dict):
            return self.memory.content
        return self.memory.content.dict()

    @property
    def memory_type(self) -> str:
        """Expose the tier name using terminology expected by integrations."""

        return self.tier

    @property
    def timestamp(self) -> datetime:
        """Return the timestamp associated with the memory access."""

        return self.memory.metadata.last_accessed

    def dict(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:  # type: ignore[override]
        """Serialise the retrieval result while expanding nested models."""

        data = super().dict(*args, **kwargs)
        data["memory"] = self.memory.dict()
        return data


__all__ = ["MemoryRetrievalResult"]

