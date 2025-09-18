from __future__ import annotations

import asyncio
import contextlib
from types import MethodType
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List

import pytest

from neuroca.memory.exceptions import MemoryManagerOperationError
from neuroca.memory.manager.consolidation import consolidate_mtm_to_ltm
from neuroca.memory.manager.consolidation_pipeline import TransactionalConsolidationPipeline
from neuroca.memory.manager.consolidation_guard import ConsolidationInFlightGuard
from neuroca.memory.manager.memory_manager import MemoryManager
from neuroca.memory.manager.events import (
    ConsolidationOutcomeEvent,
    MaintenanceEventPublisher,
)
from neuroca.memory.models.memory_item import MemoryItem, MemoryMetadata


@dataclass
class StubMTMMemory:
    id: str
    content: Dict[str, Any]
    metadata: Dict[str, Any]
    tags: List[str]
    created_at: datetime
    access_count: int


class RecordingMTMStorage:
    def __init__(self, memories: List[StubMTMMemory], *, fail_finalize: bool = False, sticky: bool = False) -> None:
        self._memories = list(memories)
        self.fail_finalize = fail_finalize
        self.sticky = sticky
        self.consolidated: List[str] = []

    async def search(self, min_priority: Any = None) -> List[StubMTMMemory]:  # noqa: ANN401
        return list(self._memories)

    async def consolidate_memory(self, memory_id: str) -> None:
        if self.fail_finalize:
            raise RuntimeError("mtm finalize failure")

        self.consolidated.append(memory_id)
        if not self.sticky:
            self._memories = [m for m in self._memories if m.id != memory_id]


class RecordingLTMStorage:
    def __init__(self) -> None:
        self.stored: List[Any] = []
        self.deleted: List[str] = []

    async def store(self, item: Any) -> str:  # noqa: ANN401
        self.stored.append(item)
        return f"ltm-{len(self.stored)}"

    async def delete(self, item_id: str) -> None:
        self.deleted.append(item_id)


class StubTier:
    def __init__(self, name: str, items: Dict[str, MemoryItem], *, fail_delete: bool = False) -> None:
        self.name = name
        self.items = dict(items)
        self.fail_delete = fail_delete
        self.initialized = False
        self.deleted: List[str] = []
        self.stores: List[str] = []
        self.retrieved: List[str] = []

    async def initialize(self) -> None:
        self.initialized = True

    async def shutdown(self) -> None:
        self.initialized = False

    async def retrieve(self, memory_id: str) -> MemoryItem:
        self.retrieved.append(memory_id)
        return self.items[memory_id]

    async def store(self, payload: MemoryItem) -> str:
        new_id = getattr(payload, "id", None) or f"{self.name}-{len(self.items) + 1}"
        self.items[new_id] = payload
        self.stores.append(new_id)
        return new_id

    async def delete(self, memory_id: str) -> None:
        if self.fail_delete:
            raise RuntimeError(f"{self.name} delete failure")

        self.deleted.append(memory_id)
        self.items.pop(memory_id, None)

    async def exists(self, memory_id: str) -> bool:
        return memory_id in self.items


@pytest.mark.asyncio
async def test_transaction_rolls_back_on_finalize_failure() -> None:
    base_created = datetime.now() - timedelta(days=30)
    mtm_memories = [
        StubMTMMemory(
            id="mtm-1",
            content={"text": "Critical incident resolved."},
            metadata={"importance": 0.95, "additional_metadata": {}},
            tags=["incident"],
            created_at=base_created,
            access_count=12,
        )
    ]

    mtm_storage = RecordingMTMStorage(mtm_memories, fail_finalize=True)
    ltm_storage = RecordingLTMStorage()
    pipeline = TransactionalConsolidationPipeline()
    guard = ConsolidationInFlightGuard(dedupe_window_seconds=0.0)

    await consolidate_mtm_to_ltm(
        mtm_storage,
        ltm_storage,
        {"consolidation_batch_size": 5},
        pipeline=pipeline,
        guard=guard,
    )

    assert ltm_storage.deleted == ["ltm-1"]
    assert mtm_storage.consolidated == []


@pytest.mark.asyncio
async def test_transaction_recovers_after_midflight_failure() -> None:
    base_created = datetime.now() - timedelta(days=28)
    mtm_memories = [
        StubMTMMemory(
            id="mtm-retry",
            content={"text": "Follow-up incident analysis."},
            metadata={"importance": 0.92, "additional_metadata": {}},
            tags=["incident"],
            created_at=base_created,
            access_count=18,
        )
    ]

    mtm_storage = RecordingMTMStorage(mtm_memories, fail_finalize=True, sticky=True)
    ltm_storage = RecordingLTMStorage()
    pipeline = TransactionalConsolidationPipeline()
    guard = ConsolidationInFlightGuard(dedupe_window_seconds=60.0)

    config = {"consolidation_batch_size": 5}

    # First attempt raises during MTM finalization which should roll back the LTM insert.
    await consolidate_mtm_to_ltm(
        mtm_storage,
        ltm_storage,
        config,
        pipeline=pipeline,
        guard=guard,
    )

    assert ltm_storage.deleted == ["ltm-1"]
    assert mtm_storage.consolidated == []

    # Allow the finalize step to succeed and retry the same consolidation.
    mtm_storage.fail_finalize = False

    await consolidate_mtm_to_ltm(
        mtm_storage,
        ltm_storage,
        config,
        pipeline=pipeline,
        guard=guard,
    )

    assert mtm_storage.consolidated == ["mtm-retry"]
    assert ltm_storage.deleted == ["ltm-1"]
    assert len(ltm_storage.stored) == 2

    # Subsequent attempts should reuse the cached result without executing again.
    await consolidate_mtm_to_ltm(
        mtm_storage,
        ltm_storage,
        config,
        pipeline=pipeline,
        guard=guard,
    )

    assert len(ltm_storage.stored) == 2
    assert mtm_storage.consolidated == ["mtm-retry"]


@pytest.mark.asyncio
async def test_pipeline_idempotent_for_duplicate_candidates() -> None:
    base_created = datetime.now() - timedelta(days=10)
    mtm_memories = [
        StubMTMMemory(
            id="mtm-dup",
            content={"text": "Recurring outage summary."},
            metadata={"importance": 0.9, "additional_metadata": {}},
            tags=["ops"],
            created_at=base_created,
            access_count=20,
        )
    ]

    mtm_storage = RecordingMTMStorage(mtm_memories, sticky=True)
    ltm_storage = RecordingLTMStorage()
    pipeline = TransactionalConsolidationPipeline()

    config = {"consolidation_batch_size": 5}

    await consolidate_mtm_to_ltm(mtm_storage, ltm_storage, config, pipeline=pipeline)
    await consolidate_mtm_to_ltm(mtm_storage, ltm_storage, config, pipeline=pipeline)

    assert len(ltm_storage.stored) == 1
    assert mtm_storage.consolidated == ["mtm-dup"]


@pytest.mark.asyncio
async def test_memory_manager_rolls_back_when_source_delete_fails() -> None:
    stm_item = MemoryItem(
        id="stm-1",
        content={"text": "Transient finding"},
        metadata=MemoryMetadata(tags={}, importance=0.8),
    )

    stm_tier = StubTier("stm", {stm_item.id: stm_item}, fail_delete=True)
    mtm_tier = StubTier("mtm", {})
    ltm_tier = StubTier("ltm", {})

    manager = MemoryManager(
        config={"maintenance_interval": 0},
        stm=stm_tier,
        mtm=mtm_tier,
        ltm=ltm_tier,
    )

    events: List[Any] = []

    async def _publish(event: Any) -> None:
        events.append(event)

    manager._event_publisher = MaintenanceEventPublisher(
        {"enabled": True}, publisher=_publish
    )

    await manager.initialize()

    with pytest.raises(MemoryManagerOperationError):
        await manager.consolidate_memory("stm-1", "stm", "ltm")

    assert "stm-1" in stm_tier.items
    assert not ltm_tier.items
    assert ltm_tier.deleted == ["stm-1"]

    failure_events = [
        event for event in events if isinstance(event, ConsolidationOutcomeEvent)
    ]
    assert failure_events, "expected failure event to be emitted"
    assert failure_events[0].status == "error"
    assert "delete" in failure_events[0].metadata.get("error", "")

    await manager.shutdown()


@pytest.mark.asyncio
async def test_consolidation_guard_caches_completed_results() -> None:
    guard = ConsolidationInFlightGuard(dedupe_window_seconds=120.0)

    first = await guard.reserve("stm:demo->mtm")
    assert first.proceed and first.reservation is not None

    async with first.reservation as reservation:
        reservation.commit("mtm-1")

    second = await guard.reserve("stm:demo->mtm")
    assert not second.proceed
    assert second.result == "mtm-1"


@pytest.mark.asyncio
async def test_consolidation_guard_waits_for_inflight_completion() -> None:
    guard = ConsolidationInFlightGuard(dedupe_window_seconds=120.0)

    first = await guard.reserve("mtm:item->ltm")
    assert first.proceed and first.reservation is not None

    async def competitor() -> Any:
        decision = await guard.reserve("mtm:item->ltm")
        assert not decision.proceed
        return decision.result

    task = asyncio.create_task(competitor())

    async with first.reservation as reservation:
        await asyncio.sleep(0)
        reservation.commit("ltm-1")

    assert await task == "ltm-1"


@pytest.mark.asyncio
async def test_consolidation_guard_wait_for_all_blocks_until_release() -> None:
    guard = ConsolidationInFlightGuard(dedupe_window_seconds=5.0)

    decision = await guard.reserve("stm:block->mtm")
    assert decision.proceed and decision.reservation is not None

    release = asyncio.Event()

    async def performer() -> None:
        assert decision.reservation is not None
        async with decision.reservation:
            await release.wait()
            decision.reservation.commit("mtm-42")

    performer_task = asyncio.create_task(performer())
    wait_task = asyncio.create_task(guard.wait_for_all(timeout=1.0))

    await asyncio.sleep(0)
    assert not wait_task.done()

    release.set()

    await asyncio.wait_for(wait_task, timeout=1.0)
    await performer_task


@pytest.mark.asyncio
async def test_memory_manager_skips_duplicate_retrieval_after_consolidation() -> None:
    stm_item = MemoryItem(
        id="stm-dup",
        content={"text": "Highly important"},
        metadata=MemoryMetadata(tags={}, importance=0.9),
    )

    stm_tier = StubTier("stm", {stm_item.id: stm_item})
    mtm_tier = StubTier("mtm", {})
    ltm_tier = StubTier("ltm", {})

    manager = MemoryManager(
        config={"maintenance_interval": 0},
        stm=stm_tier,
        mtm=mtm_tier,
        ltm=ltm_tier,
    )

    await manager.initialize()

    first_id = await manager.consolidate_memory("stm-dup", "stm", "mtm")
    second_id = await manager.consolidate_memory("stm-dup", "stm", "mtm")

    assert first_id == second_id
    assert stm_tier.retrieved == ["stm-dup"]
    assert mtm_tier.stores == [first_id]

    await manager.shutdown()


@pytest.mark.asyncio
async def test_shutdown_waits_for_inflight_consolidation() -> None:
    stm_item = MemoryItem(
        id="stm-block",
        content={"text": "Blocking memory"},
        metadata=MemoryMetadata(tags={}, importance=0.85),
    )

    stm_tier = StubTier("stm", {stm_item.id: stm_item})
    mtm_tier = StubTier("mtm", {})
    ltm_tier = StubTier("ltm", {})

    manager = MemoryManager(
        config={
            "maintenance_interval": 0,
            "shutdown_drain_timeout_seconds": 1.0,
        },
        stm=stm_tier,
        mtm=mtm_tier,
        ltm=ltm_tier,
    )

    await manager.initialize()

    store_started = asyncio.Event()
    release_store = asyncio.Event()

    original_store = mtm_tier.store
    assert callable(original_store), "MTM tier store must be callable for test setup"

    async def blocking_store(self, payload: MemoryItem) -> str:
        store_started.set()
        await release_store.wait()
        return await original_store(payload)

    mtm_tier.store = MethodType(blocking_store, mtm_tier)

    consolidate_task = asyncio.create_task(
        manager.consolidate_memory(stm_item.id, "stm", "mtm")
    )

    await asyncio.wait_for(store_started.wait(), timeout=1.0)

    shutdown_task = asyncio.create_task(manager.shutdown())

    try:
        await asyncio.sleep(0)
        assert not shutdown_task.done()

        release_store.set()

        consolidated_id = await asyncio.wait_for(consolidate_task, timeout=1.0)
        assert consolidated_id in mtm_tier.items

        await asyncio.wait_for(shutdown_task, timeout=1.0)
    finally:
        release_store.set()
        if not consolidate_task.done():
            with contextlib.suppress(Exception):
                await consolidate_task
        if not shutdown_task.done():
            shutdown_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await shutdown_task

    assert not manager._initialized
    assert not stm_tier.initialized
    assert not mtm_tier.initialized
    assert not ltm_tier.initialized
