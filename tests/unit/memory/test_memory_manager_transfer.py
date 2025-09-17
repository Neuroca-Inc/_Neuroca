import pytest

from neuroca.core.enums import MemoryTier
from neuroca.memory.backends.factory import BackendType
from neuroca.memory.manager import MemoryManager


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
