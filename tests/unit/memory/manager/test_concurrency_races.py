from __future__ import annotations

import asyncio
import inspect
from typing import Any, Callable, Dict, Optional

import pytest

from neuroca.memory.manager.memory_manager import MemoryManager
from neuroca.memory.models.memory_item import MemoryItem, MemoryMetadata


Hook = Optional[Callable[..., Any]]


class CoordinatedTier:
    """Test double that exposes coordination hooks for concurrency checks."""

    def __init__(
        self,
        name: str,
        items: Dict[str, MemoryItem],
        *,
        store_gate: asyncio.Event | None = None,
        on_retrieve: Hook = None,
        on_store: Hook = None,
    ) -> None:
        self.name = name
        self._items: Dict[str, MemoryItem] = dict(items)
        self._store_gate = store_gate
        self._on_retrieve = on_retrieve
        self._on_store = on_store
        self.initialized = False

        self.retrieve_log: list[str] = []
        self.store_log: list[str] = []
        self.delete_log: list[str] = []
        self.access_log: list[str] = []

        # Exposed synchronization primitive so tests can await store invocation.
        self.store_started: asyncio.Event = asyncio.Event()

    @property
    def items(self) -> Dict[str, MemoryItem]:
        return self._items

    async def initialize(self) -> None:  # pragma: no cover - simple flag update
        self.initialized = True

    async def shutdown(self) -> None:  # pragma: no cover - simple flag update
        self.initialized = False

    async def retrieve(self, memory_id: str) -> MemoryItem | None:
        self.retrieve_log.append(memory_id)
        await self._maybe_call(self._on_retrieve, memory_id)
        return self._items.get(memory_id)

    async def store(self, payload: Any) -> str:
        self.store_started.set()
        await self._maybe_call(self._on_store, payload)
        if self._store_gate is not None:
            await self._store_gate.wait()

        item = self._coerce_item(payload)
        new_id = f"{self.name}-{len(self._items) + 1}"
        item.id = new_id
        self._items[new_id] = item
        self.store_log.append(new_id)
        return new_id

    async def delete(self, memory_id: str) -> None:
        self.delete_log.append(memory_id)
        self._items.pop(memory_id, None)

    async def exists(self, memory_id: str) -> bool:
        return memory_id in self._items

    async def access(self, memory_id: str) -> None:
        self.access_log.append(memory_id)
        item = self._items.get(memory_id)
        if item is not None:
            item.mark_accessed()

    async def strengthen(self, memory_id: str, _: float) -> bool:  # pragma: no cover - unused helper
        return memory_id in self._items

    async def decay(self, memory_id: str, _: float) -> bool:  # pragma: no cover - unused helper
        return memory_id in self._items

    async def update(
        self,
        memory_id: str,
        *,
        content: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:  # pragma: no cover - unused helper
        if memory_id not in self._items:
            return False
        item = self._items[memory_id]
        if content:
            for key, value in content.items():
                setattr(item.content, key, value)
        if metadata:
            for key, value in metadata.items():
                setattr(item.metadata, key, value)
        return True

    async def consolidate_memory(self, memory_id: str) -> None:  # pragma: no cover - compatibility
        self._items.pop(memory_id, None)

    async def _maybe_call(self, hook: Hook, *args: Any) -> None:
        if hook is None:
            return
        result = hook(*args)
        if inspect.isawaitable(result):
            await result

    def _coerce_item(self, payload: Any) -> MemoryItem:
        if isinstance(payload, MemoryItem):
            return payload.model_copy(deep=True)
        return MemoryItem.model_validate(payload)


def _build_manager(store_gate: asyncio.Event | None = None) -> tuple[MemoryManager, CoordinatedTier, CoordinatedTier]:
    stm_item = MemoryItem(
        id="stm-1",
        content={"text": "Critical operations timeline"},
        metadata=MemoryMetadata(tags={}, importance=0.9),
    )

    stm_tier = CoordinatedTier("stm", {stm_item.id: stm_item})
    mtm_tier = CoordinatedTier("mtm", {}, store_gate=store_gate)
    ltm_tier = CoordinatedTier("ltm", {})

    manager = MemoryManager(
        config={"maintenance_interval": 0},
        stm=stm_tier,
        mtm=mtm_tier,
        ltm=ltm_tier,
    )

    return manager, stm_tier, mtm_tier


@pytest.mark.asyncio
async def test_concurrent_consolidations_share_single_execution() -> None:
    store_gate = asyncio.Event()
    manager, stm_tier, mtm_tier = _build_manager(store_gate)

    await manager.initialize()

    first_task = asyncio.create_task(manager.consolidate_memory("stm-1", "stm", "mtm"))
    await mtm_tier.store_started.wait()

    second_task = asyncio.create_task(manager.consolidate_memory("stm-1", "stm", "mtm"))
    await asyncio.sleep(0)

    assert not first_task.done()
    assert not second_task.done()

    store_gate.set()
    first_result, second_result = await asyncio.gather(first_task, second_task)

    assert first_result == second_result
    assert mtm_tier.store_log == [first_result]
    assert stm_tier.retrieve_log == ["stm-1"]
    assert stm_tier.delete_log == ["stm-1"]

    await manager.shutdown()


@pytest.mark.asyncio
async def test_retrieval_observes_source_during_inflight_consolidation() -> None:
    store_gate = asyncio.Event()
    manager, stm_tier, mtm_tier = _build_manager(store_gate)

    await manager.initialize()

    promote_task = asyncio.create_task(manager.consolidate_memory("stm-1", "stm", "mtm"))
    await mtm_tier.store_started.wait()
    assert not promote_task.done()

    in_flight = await manager.retrieve_memory("stm-1")
    assert in_flight is not None
    assert in_flight.id == "stm-1"
    assert stm_tier.access_log == ["stm-1"]

    store_gate.set()
    promoted_id = await promote_task

    assert promoted_id == mtm_tier.store_log[-1]
    assert "stm-1" not in stm_tier.items
    assert promoted_id in mtm_tier.items

    await manager.shutdown()
