"""Deterministic decay lifecycle tests with a mocked clock."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

import neuroca.memory.manager.decay as decay_module


class FixedDateTime(datetime):
    """Datetime surrogate that always returns a fixed point in time."""

    _now: datetime = datetime(2024, 1, 1, 15, 30, tzinfo=UTC)

    @classmethod
    def set_now(cls, new_now: datetime) -> None:
        if isinstance(new_now, datetime) and not isinstance(new_now, cls):
            if new_now.tzinfo is None:
                new_now = new_now.replace(tzinfo=UTC)
            new_now = cls(
                new_now.year,
                new_now.month,
                new_now.day,
                new_now.hour,
                new_now.minute,
                new_now.second,
                new_now.microsecond,
                tzinfo=new_now.tzinfo,
            )
        cls._now = new_now

    @classmethod
    def now(cls, tz=None):  # noqa: D401 - short delegate
        """Return the frozen timestamp."""

        if tz is not None:
            return cls._now.astimezone(tz)
        return cls._now

    @classmethod
    def utcnow(cls):  # noqa: D401 - short delegate
        """Return the frozen timestamp expressed in UTC."""

        return cls._now.astimezone(UTC)

    @classmethod
    def fromisoformat(cls, date_string: str):  # noqa: D401 - short delegate
        """Parse ISO strings into ``FixedDateTime`` instances."""

        parsed = datetime.fromisoformat(date_string)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return cls(
            parsed.year,
            parsed.month,
            parsed.day,
            parsed.hour,
            parsed.minute,
            parsed.second,
            parsed.microsecond,
            tzinfo=parsed.tzinfo,
        )


@pytest.fixture
def fixed_clock(monkeypatch):
    """Freeze ``datetime.now`` inside the decay module for deterministic tests."""

    FixedDateTime.set_now(FixedDateTime.fromisoformat("2024-01-01T15:30:00+00:00"))
    monkeypatch.setattr(decay_module, "datetime", FixedDateTime)
    return FixedDateTime.now(UTC)


class DummyMTMMemory:
    def __init__(self, memory_id: str, *, strength: float, importance: float, last_accessed: str):
        self.id = memory_id
        self.metadata = {"strength": strength, "importance": importance}
        self.activation = strength
        self.last_accessed = last_accessed


class DummyMTMStorage:
    def __init__(self, memories: list[DummyMTMMemory]):
        self._memories = {memory.id: memory for memory in memories}
        self.updated: dict[str, dict] = {}
        self.removed: set[str] = set()

    async def list_all(self):  # pragma: no cover - trivial passthrough
        return list(self._memories.values())

    async def update(self, memory_id: str, metadata: dict | None = None):
        metadata = metadata or {}
        memory = self._memories[memory_id]
        memory.metadata.update(metadata)
        memory.activation = memory.metadata.get("strength", memory.activation)
        self.updated[memory_id] = dict(memory.metadata)

    async def forget_memory(self, memory_id: str):
        self._memories.pop(memory_id, None)
        self.removed.add(memory_id)


class DummyLTMMemory:
    def __init__(self, memory_id: str, metadata: dict[str, object]):
        self.id = memory_id
        self.metadata = dict(metadata)
        self.strength = float(metadata.get("strength", 0.0) or 0.0)


class DummyLTMStorage:
    def __init__(self, memories: list[DummyLTMMemory]):
        self._memories = {memory.id: memory for memory in memories}
        self.updated: dict[str, dict] = {}
        self.deleted: set[str] = set()

    async def list_all(self):  # pragma: no cover - trivial passthrough
        return list(self._memories.values())

    async def update(self, *args, **kwargs):
        if args and isinstance(args[0], DummyLTMMemory):
            memory = args[0]
            self._memories[memory.id] = memory
            self.updated[memory.id] = dict(memory.metadata)
            return
        if args:
            memory_id = args[0]
            metadata = dict(kwargs.get("metadata", {}))
            memory = self._memories[memory_id]
            memory.metadata.update(metadata)
            memory.strength = float(memory.metadata.get("strength", memory.strength) or 0.0)
            self.updated[memory_id] = dict(memory.metadata)
            return
        raise TypeError("Unsupported update signature")

    async def delete(self, memory_id: str):
        self._memories.pop(memory_id, None)
        self.deleted.add(memory_id)


@pytest.mark.asyncio
async def test_decay_mtm_memories_respects_frozen_clock(fixed_clock):
    fresh = DummyMTMMemory(
        "fresh",
        strength=0.6,
        importance=0.85,
        last_accessed=(fixed_clock - timedelta(minutes=8)).isoformat(),
    )
    stale = DummyMTMMemory(
        "stale",
        strength=0.08,
        importance=0.15,
        last_accessed=(fixed_clock - timedelta(hours=6)).isoformat(),
    )

    storage = DummyMTMStorage([fresh, stale])
    original_strength = fresh.activation

    stats = await decay_module.decay_mtm_memories(
        storage,
        config={
            "strength_model": {
                "mtm": {
                    "passive_half_life_seconds": 90.0,
                    "reinforcement_half_life_seconds": 45.0,
                    "max_decay_per_cycle": 0.6,
                    "forgetting_threshold": 0.2,
                }
            }
        },
    )

    assert storage.removed == {"stale"}
    assert "fresh" in storage.updated

    updated = storage.updated["fresh"]
    assert updated["last_decay_at"] == fixed_clock.isoformat()
    assert 0.0 < updated["strength"] <= original_strength
    assert fresh.activation == pytest.approx(updated["strength"], rel=1e-6)

    assert stats == {"processed": 2, "decayed": 1, "removed": 1}


@pytest.mark.asyncio
async def test_decay_ltm_memories_respects_frozen_clock(fixed_clock):
    surviving = DummyLTMMemory(
        "ltm-keep",
        {
            "strength": 0.5,
            "importance": 0.9,
            "last_accessed_at": (fixed_clock - timedelta(minutes=30)).isoformat(),
        },
    )
    stale = DummyLTMMemory(
        "ltm-drop",
        {
            "strength": 0.04,
            "importance": 0.05,
            "last_accessed_at": (fixed_clock - timedelta(days=2)).isoformat(),
        },
    )

    storage = DummyLTMStorage([surviving, stale])

    ltm_stats = await decay_module.decay_ltm_memories(
        storage,
        config={
            "strength_model": {
                "ltm": {
                    "passive_half_life_seconds": 180.0,
                    "reinforcement_half_life_seconds": 60.0,
                    "max_decay_per_cycle": 0.5,
                    "forgetting_threshold": 0.2,
                }
            }
        },
    )

    assert storage.deleted == {"ltm-drop"}
    assert "ltm-keep" in storage.updated

    assert ltm_stats == {"processed": 2, "decayed": 1, "removed": 1}

    updated = storage.updated["ltm-keep"]
    assert updated["last_decay_at"] == fixed_clock.isoformat()
    assert 0.0 < updated["strength"] <= surviving.metadata["strength"]
    assert storage._memories["ltm-keep"].strength == pytest.approx(updated["strength"], rel=1e-6)
