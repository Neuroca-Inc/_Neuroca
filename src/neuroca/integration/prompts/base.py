"""Shared prompt template utilities for the integration layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Optional


@dataclass(slots=True)
class PromptMetadata:
    """Basic metadata container for prompt templates."""

    name: Optional[str] = None
    description: Optional[str] = None
    tags: list[str] = field(default_factory=list)
    version: str = "1.0.0"


class BasePromptTemplate:
    """Minimal base class shared by prompt implementations."""

    def __init__(
        self,
        template_id: Optional[str] = None,
        metadata: Optional[PromptMetadata | dict[str, Any]] = None,
        created_at: Optional[datetime] = None,
    ) -> None:
        self.template_id = template_id or "prompt-template"
        if isinstance(metadata, dict):
            metadata = PromptMetadata(**metadata)
        self.metadata = metadata or PromptMetadata(name=self.template_id)
        now = datetime.now(UTC)
        self.created_at = created_at or now
        self.updated_at = self.created_at

    def touch(self) -> None:
        """Record that the template has been updated."""

        self.updated_at = datetime.now(UTC)


__all__ = ["BasePromptTemplate", "PromptMetadata"]
