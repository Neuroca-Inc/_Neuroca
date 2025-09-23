"""Unit tests covering manual decay operations on memory tiers."""

from __future__ import annotations

import pytest

from neuroca.memory.backends import BackendType
from neuroca.memory.tiers.ltm.core import LongTermMemoryTier
from neuroca.memory.tiers.mtm.core import MediumTermMemoryTier
from neuroca.memory.tiers.stm.core import ShortTermMemoryTier

TIERS = (
    ShortTermMemoryTier,
    MediumTermMemoryTier,
    LongTermMemoryTier,
)


@pytest.mark.asyncio
@pytest.mark.parametrize("tier_cls", TIERS)
async def test_decay_reduces_strength(tier_cls) -> None:
    """Ensure tier-specific decay decreases the stored strength value."""

    tier = tier_cls(backend_type=BackendType.MEMORY)
    await tier.initialize()
    try:
        memory_id = await tier.store(
            {"text": "decay candidate"},
            {"importance": 0.9, "tags": {"suite": "decay"}, "access_count": 5},
        )
        baseline = await tier.get_memory_strength(memory_id)
        changed = await tier.decay(memory_id, decay_amount=0.2)
        updated = await tier.get_memory_strength(memory_id)
    finally:
        await tier.shutdown()

    assert changed is True
    assert updated < baseline


@pytest.mark.asyncio
async def test_decay_rejects_negative_amount() -> None:
    """Negative decay magnitudes should be rejected early."""

    tier = ShortTermMemoryTier(backend_type=BackendType.MEMORY)
    await tier.initialize()
    memory_id = await tier.store(
        {"text": "negative"},
        {"importance": 0.5, "tags": {"suite": "decay"}},
    )
    try:
        with pytest.raises(ValueError):
            await tier.decay(memory_id, decay_amount=-0.1)
    finally:
        await tier.shutdown()
