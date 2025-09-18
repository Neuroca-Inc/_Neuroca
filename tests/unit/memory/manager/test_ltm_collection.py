"""Tests for defensive LTM collection helpers in the memory manager."""

from __future__ import annotations

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
