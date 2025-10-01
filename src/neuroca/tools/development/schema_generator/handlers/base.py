"""Interface for schema source handlers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional


class SourceHandler(ABC):
    """Define a contract for converting sources into schema dictionaries."""

    @abstractmethod
    def generate(self, source: Any, namespace: Optional[str] = None) -> dict[str, Any]:
        """Produce schema data for the provided source."""


__all__ = ["SourceHandler"]
