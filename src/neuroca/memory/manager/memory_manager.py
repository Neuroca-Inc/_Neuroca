"""Asynchronous memory manager implementation using modular mixins."""

from __future__ import annotations

from neuroca.memory.manager.components import (
    LOGGER,
    MemoryManagerBase,
    MemoryManagerConsolidationMixin,
    MemoryManagerContextMixin,
    MemoryManagerDecayMixin,
    MemoryManagerLifecycleMixin,
    MemoryManagerLegacyMixin,
    MemoryManagerOperationsMixin,
    MemoryManagerQualityMixin,
    MemoryManagerRelationshipsMixin,
    MemoryManagerStatsMixin,
    MemoryManagerStrengthMixin,
    MemoryManagerVisibilityMixin,
)

logger = LOGGER


class MemoryManager(
    MemoryManagerContextMixin,
    MemoryManagerRelationshipsMixin,
    MemoryManagerOperationsMixin,
    MemoryManagerVisibilityMixin,
    MemoryManagerQualityMixin,
    MemoryManagerStatsMixin,
    MemoryManagerStrengthMixin,
    MemoryManagerDecayMixin,
    MemoryManagerConsolidationMixin,
    MemoryManagerLegacyMixin,
    MemoryManagerLifecycleMixin,
    MemoryManagerBase,
):
    """Coordinate tiered memory operations across storage implementations."""

    STM_TIER = "stm"
    MTM_TIER = "mtm"
    LTM_TIER = "ltm"


__all__ = ["MemoryManager"]
