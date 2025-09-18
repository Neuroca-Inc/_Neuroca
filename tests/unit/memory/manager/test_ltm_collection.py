"""Tests for defensive LTM collection helpers in the memory manager."""

from __future__ import annotations

from collections import Counter

import pytest

from neuroca.memory.manager.memory_manager import MemoryManager


class _BaseTier:
    def __init__(self, name: str) -> None:
        self.name = name
        self.config = {"max_capacity": 1}

    async def initialize(self) -> None:  # pragma: no cover - simple stub
        return None

    async def shutdown(self) -> None:  # pragma: no cover - simple stub
        return None

    async def count(self, _filters=None) -> int:  # pragma: no cover - compatibility
        return 0


class _StubLtmTier(_BaseTier):
    def __init__(self) -> None:
        super().__init__("ltm")
        self.items = ["ltm-entry"]
        self.retrieve_calls = 0
        self.list_all = ["not-callable"]  # type: ignore[assignment]

    def retrieve_all(self, limit=None):  # pragma: no cover - synchronous stub
        del limit
        self.retrieve_calls += 1
        return list(self.items)


class _CachingAwareLtmTier(_BaseTier):
    def __init__(self) -> None:
        super().__init__("ltm")
        self.items = ["ltm-entry"]
        self.retrieve_calls = 0
        self.lookup_counts: Counter[str] = Counter()
        self._non_callable = ["not-callable"]

    def __getattribute__(self, name: str):  # type: ignore[override]
        if name in {"list_all", "retrieve_all", "list"}:
            lookup_counts = object.__getattribute__(self, "lookup_counts")
            lookup_counts[name] += 1
            if name == "retrieve_all":
                return object.__getattribute__(self, "_callable_retrieve")
            if name == "list":
                return None
            return object.__getattribute__(self, "_non_callable")
        return object.__getattribute__(self, name)

    def _callable_retrieve(self, limit=None):  # pragma: no cover - synchronous stub
        del limit
        self.retrieve_calls += 1
        return list(object.__getattribute__(self, "items"))


@pytest.mark.asyncio
async def test_collect_ltm_memories_skips_non_callable_handlers() -> None:
    stm = _BaseTier("stm")
    mtm = _BaseTier("mtm")
    ltm = _StubLtmTier()

    manager = MemoryManager(
        config={"maintenance_interval": 0, "resource_limits": {}},
        stm=stm,
        mtm=mtm,
        ltm=ltm,
    )

    await manager.initialize()
    try:
        collected = await manager._collect_ltm_memories(limit=5)
        assert collected == ltm.items
        assert ltm.retrieve_calls == 1
    finally:
        await manager.shutdown()


@pytest.mark.asyncio
async def test_collect_ltm_memories_caches_handler_resolution() -> None:
    stm = _BaseTier("stm")
    mtm = _BaseTier("mtm")
    ltm = _CachingAwareLtmTier()

    manager = MemoryManager(
        config={"maintenance_interval": 0, "resource_limits": {}},
        stm=stm,
        mtm=mtm,
        ltm=ltm,
    )

    await manager.initialize()
    try:
        first = await manager._collect_ltm_memories(limit=3)
        second = await manager._collect_ltm_memories(limit=3)

        assert first == ltm.items
        assert second == ltm.items
        assert ltm.lookup_counts["list_all"] == 1
        assert ltm.lookup_counts["retrieve_all"] == 1
        assert ltm.retrieve_calls == 2
    finally:
        await manager.shutdown()
