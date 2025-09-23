"""Shared helper utilities for memory manager CRUD operations."""

from __future__ import annotations

from typing import Any, List

from neuroca.core.enums import MemoryTier
from neuroca.memory.models.memory_item import MemoryItem


class MemoryManagerOperationSupportMixin:
    """Provide shared helper utilities for CRUD-oriented mixins."""

    def _tier_iteration_order(self) -> List[str]:
        """Return the canonical iteration order for memory tiers."""

        return [self.STM_TIER, self.MTM_TIER, self.LTM_TIER]

    def _resolve_tier_key(self, tier: str | MemoryTier) -> str:
        """Normalise a tier identifier into its canonical storage key."""

        if isinstance(tier, MemoryTier):
            return tier.storage_key
        return MemoryTier.from_string(str(tier)).storage_key

    def _coerce_memory_item(self, candidate: Any) -> MemoryItem:
        """Return a :class:`MemoryItem` instance for ``candidate``."""

        if isinstance(candidate, MemoryItem):
            return candidate
        return MemoryItem.model_validate(candidate)


__all__ = ["MemoryManagerOperationSupportMixin"]
