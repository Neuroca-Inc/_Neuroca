import asyncio
from typing import Any, Dict

import pytest

from neuroca.memory.exceptions import MemoryBackpressureError
from neuroca.memory.manager.backpressure import BackpressureController
from neuroca.memory.manager.memory_manager import MemoryManager


class DummyTier:
    def __init__(self, name: str) -> None:
        self.name = name
        self.initialized = False
        self._items: Dict[str, Dict[str, Any]] = {}

    async def initialize(self) -> None:
        self.initialized = True

    async def shutdown(self) -> None:
        self.initialized = False

    async def count(self, _filters: Any | None = None) -> int:
        return len(self._items)

    async def cleanup(self) -> int:
        return 0

    async def store(self, payload: Dict[str, Any], memory_id: str | None = None) -> str:
        memory_id = memory_id or f"{self.name}-{len(self._items) + 1}"
        self._items[memory_id] = dict(payload)
        return memory_id

    async def retrieve(self, memory_id: str) -> Dict[str, Any] | None:
        item = self._items.get(memory_id)
        return dict(item) if item is not None else None

    async def delete(self, memory_id: str) -> bool:
        return self._items.pop(memory_id, None) is not None

    async def update(
        self,
        memory_id: str,
        *,
        content: Dict[str, Any] | None = None,
        metadata: Dict[str, Any] | None = None,
    ) -> bool:
        if memory_id not in self._items:
            return False
        entry = self._items[memory_id]
        if content:
            entry.setdefault("content", {}).update(content)
        if metadata:
            entry.setdefault("metadata", {}).update(metadata)
        return True

    async def access(self, _memory_id: str) -> None:
        return None


class BlockingTier(DummyTier):
    def __init__(
        self,
        name: str,
        start_event: asyncio.Event,
        release_event: asyncio.Event,
    ) -> None:
        super().__init__(name)
        self._start_event = start_event
        self._release_event = release_event
        self._block_next = True

    async def store(self, payload: Dict[str, Any], memory_id: str | None = None) -> str:
        if self._block_next:
            self._block_next = False
            self._start_event.set()
            await self._release_event.wait()
        return await super().store(payload, memory_id=memory_id)


@pytest.mark.asyncio
async def test_backpressure_allows_within_limit() -> None:
    controller = BackpressureController.from_config({"stm": {"max_inflight": 2}})

    async with controller.slot("stm"):
        snapshot = controller.snapshot()["stm"]
        assert snapshot["inflight"] == 1
        assert snapshot["queued"] == 0

    assert controller.snapshot()["stm"]["inflight"] == 0


@pytest.mark.asyncio
async def test_backpressure_queues_until_slot_released() -> None:
    controller = BackpressureController.from_config(
        {"stm": {"max_inflight": 1, "max_queue": 1, "overflow_policy": "queue"}}
    )

    first_started = asyncio.Event()
    release_first = asyncio.Event()
    second_started = asyncio.Event()

    async def holder() -> None:
        async with controller.slot("stm"):
            first_started.set()
            await release_first.wait()

    async def queued() -> None:
        async with controller.slot("stm"):
            second_started.set()

    task1 = asyncio.create_task(holder())
    await first_started.wait()

    queued_task = asyncio.create_task(queued())
    await asyncio.sleep(0)
    snapshot = controller.snapshot()["stm"]
    assert snapshot["queued"] == 1

    release_first.set()
    await queued_task
    await task1

    final_snapshot = controller.snapshot()["stm"]
    assert final_snapshot == {"inflight": 0, "queued": 0}


@pytest.mark.asyncio
async def test_backpressure_rejects_when_queue_full() -> None:
    controller = BackpressureController.from_config(
        {"stm": {"max_inflight": 1, "max_queue": 0, "overflow_policy": "queue"}}
    )

    started = asyncio.Event()
    release = asyncio.Event()

    async def holder() -> None:
        async with controller.slot("stm"):
            started.set()
            await release.wait()

    task = asyncio.create_task(holder())
    await started.wait()

    with pytest.raises(MemoryBackpressureError):
        async with controller.slot("stm"):
            pass

    release.set()
    await task


@pytest.mark.asyncio
async def test_backpressure_reject_policy() -> None:
    controller = BackpressureController.from_config(
        {"stm": {"max_inflight": 1, "overflow_policy": "reject"}}
    )

    started = asyncio.Event()
    release = asyncio.Event()

    async def holder() -> None:
        async with controller.slot("stm"):
            started.set()
            await release.wait()

    task = asyncio.create_task(holder())
    await started.wait()

    with pytest.raises(MemoryBackpressureError):
        async with controller.slot("stm"):
            pass

    release.set()
    await task


@pytest.mark.asyncio
async def test_backpressure_times_out_waiting_for_slot() -> None:
    controller = BackpressureController.from_config(
        {
            "stm": {
                "max_inflight": 1,
                "max_queue": 1,
                "overflow_policy": "queue",
                "wait_timeout_seconds": 0.05,
            }
        }
    )

    started = asyncio.Event()
    release = asyncio.Event()

    async def holder() -> None:
        async with controller.slot("stm"):
            started.set()
            await release.wait()

    task = asyncio.create_task(holder())
    await started.wait()

    async def attempt() -> None:
        async with controller.slot("stm"):
            pass

    with pytest.raises(MemoryBackpressureError):
        await attempt()

    release.set()
    await task


@pytest.mark.asyncio
async def test_memory_manager_rejects_when_backpressure_forces_rejection() -> None:
    started = asyncio.Event()
    release = asyncio.Event()
    stm = BlockingTier("stm", started, release)
    config = {
        "backpressure": {
            "stm": {
                "max_inflight": 1,
                "overflow_policy": "reject",
            }
        }
    }

    manager = MemoryManager(
        config=config,
        stm=stm,
        mtm=DummyTier("mtm"),
        ltm=DummyTier("ltm"),
    )

    await manager.initialize()

    first_task = asyncio.create_task(manager.add_memory("one", importance=0.5))
    await started.wait()

    with pytest.raises(MemoryBackpressureError):
        await manager.add_memory("two", importance=0.5)

    release.set()
    await first_task
    await manager.shutdown()


@pytest.mark.asyncio
async def test_memory_manager_queues_when_backpressure_allows_queueing() -> None:
    started = asyncio.Event()
    release = asyncio.Event()
    stm = BlockingTier("stm", started, release)
    config = {
        "backpressure": {
            "stm": {
                "max_inflight": 1,
                "max_queue": 1,
                "overflow_policy": "queue",
            }
        }
    }

    manager = MemoryManager(
        config=config,
        stm=stm,
        mtm=DummyTier("mtm"),
        ltm=DummyTier("ltm"),
    )

    await manager.initialize()

    first_task = asyncio.create_task(manager.add_memory("one", importance=0.5))
    await started.wait()

    second_task = asyncio.create_task(manager.add_memory("two", importance=0.5))
    await asyncio.sleep(0.05)
    assert not second_task.done()

    release.set()

    second_id = await second_task
    assert second_id.startswith("stm-")

    await first_task
    await manager.shutdown()
