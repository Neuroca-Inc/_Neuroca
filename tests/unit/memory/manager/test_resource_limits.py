import asyncio
from typing import Any

import pytest

from neuroca.memory.exceptions import MemoryCapacityError
from neuroca.memory.manager.memory_manager import MemoryManager
from neuroca.memory.manager.resource_limits import ResourceLimitWatchdog, TierResourceLimit


class FakeTier:
    def __init__(
        self,
        name: str,
        *,
        count: int = 0,
        cleanup_removes: int = 0,
        store_delay: float = 0.0,
    ) -> None:
        self.name = name
        self._count = count
        self._cleanup_removes = cleanup_removes
        self.store_delay = store_delay
        self.cleanup_calls = 0
        self.initialized = False
        self.stored_payloads: list[Any] = []

    async def initialize(self) -> None:
        self.initialized = True

    async def shutdown(self) -> None:
        self.initialized = False

    async def count(self, _filters: Any | None = None) -> int:
        return self._count

    async def cleanup(self) -> int:
        self.cleanup_calls += 1
        removed = min(self._count, self._cleanup_removes)
        self._count -= removed
        return removed

    async def store(self, payload: Any) -> str:
        if self.store_delay:
            await asyncio.sleep(self.store_delay)
        self._count += 1
        self.stored_payloads.append(payload)
        return f"{self.name}-{len(self.stored_payloads)}"

    async def retrieve(self, _memory_id: str) -> Any | None:  # noqa: ANN401
        return None

    async def access(self, _memory_id: str) -> None:
        return None


@pytest.mark.asyncio
async def test_watchdog_allows_ingest_below_capacity() -> None:
    limit = TierResourceLimit.from_config("stm", {"max_items": 5})
    watchdog = ResourceLimitWatchdog({"stm": limit})
    tier = FakeTier("stm", count=3)

    await watchdog.ensure_capacity("stm", tier)
    memory_id = await watchdog.store("stm", tier, {"id": "stm-1"})

    assert memory_id == "stm-1"
    assert tier._count == 4  # noqa: SLF001


@pytest.mark.asyncio
async def test_watchdog_rejects_when_capacity_reached() -> None:
    limit = TierResourceLimit.from_config("stm", {"max_items": 1, "overflow_policy": "reject"})
    watchdog = ResourceLimitWatchdog({"stm": limit})
    tier = FakeTier("stm", count=1)

    with pytest.raises(MemoryCapacityError):
        await watchdog.ensure_capacity("stm", tier)


@pytest.mark.asyncio
async def test_watchdog_attempts_eviction_then_allows_store() -> None:
    limit = TierResourceLimit.from_config(
        "stm",
        {"max_items": 2, "overflow_policy": "evict", "max_eviction_attempts": 2},
    )
    watchdog = ResourceLimitWatchdog({"stm": limit})
    tier = FakeTier("stm", count=3, cleanup_removes=2)

    await watchdog.ensure_capacity("stm", tier)
    assert tier.cleanup_calls == 1
    assert tier._count == 1  # noqa: SLF001

    memory_id = await watchdog.store("stm", tier, {"id": "stm-evicted"})
    assert memory_id.startswith("stm-")
    assert tier._count == 2  # noqa: SLF001


@pytest.mark.asyncio
async def test_watchdog_enforces_store_timeout() -> None:
    limit = TierResourceLimit.from_config(
        "stm",
        {"ingest_timeout_seconds": 0.01},
    )
    watchdog = ResourceLimitWatchdog({"stm": limit})
    tier = FakeTier("stm", store_delay=0.05)

    with pytest.raises(asyncio.TimeoutError):
        await watchdog.store("stm", tier, {"id": "slow"})


@pytest.mark.asyncio
async def test_memory_manager_rejects_when_capacity_guard_hits_limit() -> None:
    config = {
        "resource_limits": {
            "stm": {
                "max_items": 1,
                "overflow_policy": "reject",
            }
        }
    }
    stm = FakeTier("stm", count=1)
    manager = MemoryManager(config=config, stm=stm, mtm=FakeTier("mtm"), ltm=FakeTier("ltm"))

    await manager.initialize()
    with pytest.raises(MemoryCapacityError):
        await manager.add_memory("full", importance=0.4)

    await manager.shutdown()


@pytest.mark.asyncio
async def test_memory_manager_runs_cleanup_to_make_room() -> None:
    config = {
        "resource_limits": {
            "stm": {
                "max_items": 2,
                "overflow_policy": "evict",
                "max_eviction_attempts": 2,
            }
        }
    }
    stm = FakeTier("stm", count=3, cleanup_removes=2)
    manager = MemoryManager(config=config, stm=stm, mtm=FakeTier("mtm"), ltm=FakeTier("ltm"))

    await manager.initialize()
    memory_id = await manager.add_memory("ok", importance=0.4)

    assert memory_id.startswith("stm-")
    assert stm.cleanup_calls == 1
    assert stm._count == 2  # noqa: SLF001

    await manager.shutdown()
