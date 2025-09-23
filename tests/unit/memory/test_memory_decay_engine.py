"""Unit tests for the time-aware memory decay engine."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from neuroca.core.events.handlers import FunctionEventHandler, event_bus
from neuroca.core.memory.episodic_memory import EpisodicMemory
from neuroca.core.memory.working_memory import WorkingMemory
from neuroca.memory.memory_decay import MemoryDecay, MemoryDecayEvent
from neuroca.memory.semantic_memory import RelationshipType, SemanticMemory


class EventCapture:
    """Helper context manager that records published memory decay events."""

    def __init__(self):
        self.events: list[MemoryDecayEvent] = []
        self._handler: FunctionEventHandler | None = None

    def __enter__(self):
        self._handler = FunctionEventHandler(
            self._record_event,
            MemoryDecayEvent,
            name="test_memory_decay_event_capture",
        )
        event_bus.register_handler(self._handler)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self._handler:
            event_bus.unregister_handler(self._handler)
        self._handler = None

    def _record_event(self, event: MemoryDecayEvent, _context):  # pragma: no cover - thin wrapper
        self.events.append(event)


def _aging_timestamp(minutes: int) -> datetime:
    return datetime.now(UTC) - timedelta(minutes=minutes)


def test_process_removes_weak_working_memories_and_emits_events():
    working = WorkingMemory(capacity=10, decay_rate=0.0)

    stale_id = working.store("stale", activation=0.4)
    retained_id = working.store("retain", activation=0.9)

    working._chunks[stale_id].last_accessed = _aging_timestamp(180)  # type: ignore[attr-defined]
    working._chunks[retained_id].last_accessed = _aging_timestamp(1)  # type: ignore[attr-defined]
    working._chunks[retained_id].metadata["importance"] = 0.9  # type: ignore[attr-defined]

    decay = MemoryDecay(
        working_memory=working,
        config={
            "working": {"half_life_seconds": 30, "min_activation": 0.2, "max_decay_per_run": 0.7},
        },
    )

    with EventCapture() as capture:
        stats = decay.process()

    assert stale_id not in working._chunks  # type: ignore[attr-defined]
    assert working._chunks[retained_id].activation < 0.9  # type: ignore[attr-defined]

    working_stats = stats["per_tier"]["working"]
    assert working_stats["processed"] == 2
    assert working_stats["removed"] == 1
    assert working_stats["decayed"] == 1
    assert len(capture.events) == working_stats["events"] == 2
    assert {event.metadata["status"] for event in capture.events} == {"removed", "decayed"}


def test_process_updates_episodic_and_semantic_tiers():
    episodic = EpisodicMemory(decay_rate=0.0)
    semantic = SemanticMemory()

    episodic_id = episodic.store(
        "low salience entry",
        emotional_salience=0.2,
        metadata={"emotional_salience": 0.2, "importance": 0.1},
    )
    episodic._chunks[episodic_id].last_accessed = _aging_timestamp(120)  # type: ignore[attr-defined]

    concept_id = semantic.store(
        {
            "name": "Transient fact",
            "properties": {
                "stability": 0.2,
                "importance": 0.2,
                "last_accessed_at": _aging_timestamp(240).isoformat(),
            },
        }
    )
    relationship_id = semantic.store(
        {
            "source_id": concept_id,
            "target_id": concept_id,
            "relationship_type": RelationshipType.RELATED_TO.value,
            "strength": 0.15,
            "metadata": {"importance": 0.1, "last_accessed_at": _aging_timestamp(180).isoformat()},
        }
    )

    decay = MemoryDecay(
        episodic_memory=episodic,
        semantic_memory=semantic,
        config={
            "episodic": {
                "half_life_seconds": 60,
                "min_activation": 0.05,
                "max_decay_per_run": 1.0,
            },
            "semantic": {
                "concept_half_life_seconds": 600,
                "relationship_half_life_seconds": 300,
                "min_concept_strength": 0.15,
                "min_relationship_strength": 0.1,
                "max_decay_per_run": 0.95,
            },
        },
    )

    with EventCapture() as capture:
        stats = decay.process()

    episodic_stats = stats["per_tier"]["episodic"]
    semantic_stats = stats["per_tier"]["semantic"]

    assert episodic_stats["processed"] == 1
    assert episodic_stats["removed"] == 1
    assert semantic_stats["processed"] == 2
    assert semantic_stats["removed"] == 2

    assert not episodic._chunks  # type: ignore[attr-defined]
    assert not semantic.retrieve_all_concepts()
    assert not semantic.retrieve_all_relationships()

    statuses = {event.metadata["status"] for event in capture.events}
    assert statuses == {"removed"}

    event_ids = {event.memory_id for event in capture.events}
    assert relationship_id in event_ids


@pytest.mark.asyncio
async def test_process_async_allows_event_loop_execution():
    working = WorkingMemory(capacity=5, decay_rate=0.0)
    mem_id = working.store("async", activation=0.6)
    working._chunks[mem_id].last_accessed = _aging_timestamp(90)  # type: ignore[attr-defined]

    decay = MemoryDecay(
        working_memory=working,
        config={"working": {"half_life_seconds": 30, "min_activation": 0.1}},
    )

    with EventCapture() as capture:
        stats = await decay.process_async()

    assert stats["total_processed"] == 1
    assert capture.events

    with pytest.raises(RuntimeError):
        decay.process()

