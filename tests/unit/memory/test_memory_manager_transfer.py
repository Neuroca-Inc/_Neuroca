"""Unit tests exercising cross-tier transfer operations in the memory manager."""

from __future__ import annotations

import pytest

from neuroca.core.enums import MemoryTier
from neuroca.memory.backends.factory import BackendType
from neuroca.memory.exceptions import InvalidTierError, MemoryNotFoundError
from neuroca.memory.manager import MemoryManager
from neuroca.memory.models.memory_item import MemoryItem


@pytest.mark.asyncio
async def test_transfer_memory_moves_between_tiers():
    manager = MemoryManager(
        stm_storage_type=BackendType.MEMORY,
        mtm_storage_type=BackendType.MEMORY,
        ltm_storage_type=BackendType.MEMORY,
    )
    await manager.initialize()

    memory_id = await manager.add_memory(
        content="transfer me",
        importance=0.6,
        initial_tier=MemoryTier.STM.storage_key,
    )

    moved = await manager.transfer_memory(memory_id, MemoryTier.MTM)

    assert moved is not None
    assert moved.metadata.tier == MemoryTier.MTM.storage_key

    mtm_item = await manager.retrieve_memory(memory_id, tier=MemoryTier.MTM.storage_key)
    stm_item = await manager.retrieve_memory(memory_id, tier=MemoryTier.STM.storage_key)

    assert mtm_item is not None
    assert stm_item is None

    await manager.shutdown()


@pytest.mark.asyncio
async def test_transfer_memory_rejects_unknown_target_tier():
    """Ensure transferring to an invalid tier raises an informative error."""

    manager = MemoryManager(
        stm_storage_type=BackendType.MEMORY,
        mtm_storage_type=BackendType.MEMORY,
        ltm_storage_type=BackendType.MEMORY,
    )
    await manager.initialize()

    try:
        memory_id = await manager.add_memory(
            content="invalid tier", importance=0.9, initial_tier=MemoryTier.STM.storage_key
        )

        with pytest.raises(InvalidTierError):
            await manager.transfer_memory(memory_id, "invalid-tier")
    finally:
        await manager.shutdown()


@pytest.mark.asyncio
async def test_transfer_memory_missing_item_raises_not_found():
    """Transferring a memory that no longer exists should fail fast."""

    manager = MemoryManager(
        stm_storage_type=BackendType.MEMORY,
        mtm_storage_type=BackendType.MEMORY,
        ltm_storage_type=BackendType.MEMORY,
    )
    await manager.initialize()

    try:
        with pytest.raises(MemoryNotFoundError):
            await manager.transfer_memory("missing-id", MemoryTier.MTM)
    finally:
        await manager.shutdown()


@pytest.mark.asyncio
async def test_transfer_memory_updates_metadata_and_clears_working_buffer():
    """Transfers should refresh metadata and evict items from working memory."""

    manager = MemoryManager(
        stm_storage_type=BackendType.MEMORY,
        mtm_storage_type=BackendType.MEMORY,
        ltm_storage_type=BackendType.MEMORY,
    )
    await manager.initialize()

    try:
        manager._current_context = {"text": "prime working memory"}
        memory_id = await manager.add_memory(
            content="promote me",
            importance=0.95,
            initial_tier=MemoryTier.STM.storage_key,
        )

        stm_snapshot = await manager.retrieve_memory(memory_id, tier=MemoryTier.STM.storage_key)
        baseline_item = MemoryItem.model_validate(stm_snapshot)
        assert baseline_item.metadata.updated_at is None
        assert memory_id in manager._working_memory.item_ids

        buffer = manager._working_memory

        class _WorkingMemoryWrapper:
            """Provide `contains` while delegating to the underlying buffer."""

            def __init__(self, inner_buffer):
                self._inner_buffer = inner_buffer

            def contains(self, candidate: str) -> bool:
                """Return whether ``candidate`` is stored in the buffer."""

                return candidate in self._inner_buffer.item_ids

            def remove_item(self, memory_id: str) -> bool:
                """Delegate removal to the original buffer."""

                return self._inner_buffer.remove_item(memory_id)

            def __getattr__(self, name: str):
                return getattr(self._inner_buffer, name)

        manager._working_memory = _WorkingMemoryWrapper(buffer)

        transferred = await manager.transfer_memory(memory_id, MemoryTier.MTM)

        assert transferred.metadata.tier == MemoryTier.MTM.storage_key
        assert transferred.metadata.updated_at is not None
        assert memory_id not in manager._working_memory.item_ids
    finally:
        await manager.shutdown()
