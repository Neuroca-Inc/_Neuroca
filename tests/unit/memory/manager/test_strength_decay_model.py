"""Unit coverage for the strength/decay balancing model."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from neuroca.memory.backends import MemoryTier
from neuroca.memory.manager.decay import decay_mtm_memories, strengthen_memory
from neuroca.memory.manager.strength_decay import StrengthDecayModel


class FakeMemory:
    def __init__(self, memory_id: str, *, strength: float, importance: float, last_accessed: datetime):
        self.id = memory_id
        self.metadata = {"strength": strength, "importance": importance}
        self.activation = strength
        self.last_accessed = last_accessed


class FakeMTMStorage:
    def __init__(self, memories: list[FakeMemory]):
        self._memories = {memory.id: memory for memory in memories}
        self.updated: dict[str, dict] = {}
        self.removed: set[str] = set()

    async def list_all(self):  # pragma: no cover - simple passthrough
        return list(self._memories.values())

    async def update(self, memory_id: str, metadata: dict | None = None):
        memory = self._memories[memory_id]
        if metadata:
            memory.metadata.update(metadata)
            memory.activation = memory.metadata.get("strength", memory.activation)
            self.updated[memory_id] = metadata

    async def forget_memory(self, memory_id: str):
        self._memories.pop(memory_id, None)
        self.removed.add(memory_id)

    async def retrieve(self, memory_id: str):
        return self._memories.get(memory_id)


@pytest.mark.parametrize(
    "reinforcement_amount",
    [0.2, 0.6],
)
def test_strength_decay_model_reinforcement_competes_with_decay(reinforcement_amount: float):
    model = StrengthDecayModel(
        "mtm",
        overrides={
            "reinforcement_half_life_seconds": 60.0,
            "passive_half_life_seconds": 120.0,
            "max_reinforcement_step": 0.5,
        },
    )

    now = datetime.now(UTC)
    state = model.state_from_metadata({"strength": 0.08, "importance": 0.4}, now=now)

    baseline = state.strength
    state = model.apply_reinforcement(state, reinforcement_amount, now=now)
    peak = state.strength
    assert peak > baseline
    assert peak <= model.max_strength

    # Allow reinforcement to decay away
    later = now + timedelta(minutes=10)
    state = model.apply_passive_decay(state, now=later)
    assert state.strength < model.max_strength

    much_later = now + timedelta(hours=2)
    state = model.apply_passive_decay(state, now=much_later)
    assert state.strength < peak
    assert state.reinforcement_level < 1e-3


def test_strength_decay_model_low_importance_eventually_drops_below_threshold():
    model = StrengthDecayModel(
        "mtm",
        overrides={
            "reinforcement_half_life_seconds": 45.0,
            "passive_half_life_seconds": 120.0,
        },
    )

    now = datetime.now(UTC)
    state = model.state_from_metadata({"strength": 0.09, "importance": 0.05}, now=now)
    state = model.apply_reinforcement(state, 0.3, now=now)
    state = model.apply_passive_decay(state, now=now + timedelta(hours=3))
    state = model.apply_passive_decay(state, now=now + timedelta(hours=6))
    assert state.strength <= model.forgetting_threshold_for(state.importance)


@pytest.mark.asyncio
async def test_decay_mtm_memories_updates_metadata_and_prunes_weak_entries():
    now = datetime.now(UTC)
    fresh = FakeMemory("keep", strength=0.4, importance=0.7, last_accessed=now)
    stale = FakeMemory("drop", strength=0.05, importance=0.1, last_accessed=now - timedelta(hours=6))

    storage = FakeMTMStorage([fresh, stale])
    stats = await decay_mtm_memories(
        storage,
        config={"strength_model": {"mtm": {"reinforcement_half_life_seconds": 30}}},
    )

    assert "drop" in storage.removed
    assert "keep" in storage.updated

    updated_metadata = storage.updated["keep"]
    assert "reinforcement_level" in updated_metadata
    assert "last_decay_at" in updated_metadata
    assert updated_metadata["strength"] <= fresh.activation

    assert stats == {"processed": 2, "decayed": 1, "removed": 1}


@pytest.mark.asyncio
async def test_strengthen_memory_uses_balancer_for_mtm():
    now = datetime.now(UTC)
    memory = FakeMemory("memory-1", strength=0.08, importance=0.6, last_accessed=now)
    storage = FakeMTMStorage([memory])

    await strengthen_memory(
        "memory-1",
        MemoryTier.MTM,
        mtm_storage=storage,
        strengthen_amount=0.4,
        config={"strength_model": {"mtm": {"reinforcement_half_life_seconds": 45}}},
    )

    assert "memory-1" in storage.updated
    metadata = storage._memories["memory-1"].metadata
    assert metadata["strength"] > 0.08
    assert metadata["reinforcement_level"] > 0
    assert metadata["reinforcement_count"] >= 1
