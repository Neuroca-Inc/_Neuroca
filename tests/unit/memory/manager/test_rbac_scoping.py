from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from neuroca.core.exceptions import MemoryAccessDeniedError
from neuroca.memory.backends.factory import BackendType
from neuroca.memory.manager import MemoryManager
from neuroca.memory.manager.scoping import MemoryRetrievalScope
from neuroca.memory.models.memory_item import MemoryItem


@pytest.mark.asyncio
async def test_retrieve_memory_requires_matching_scope():
    manager = MemoryManager(
        stm_storage_type=BackendType.MEMORY,
        mtm_storage_type=BackendType.MEMORY,
        ltm_storage_type=BackendType.MEMORY,
    )
    await manager.initialize()

    memory_id = await manager.add_memory(
        content="confidential",
        metadata={"user_id": "alice"},
    )

    try:
        allowed = MemoryRetrievalScope.for_user("alice")
        memory = await manager.retrieve_memory(memory_id, scope=allowed)
        assert memory.metadata.user_id == "alice"

        forbidden = MemoryRetrievalScope.for_user("bob")
        with pytest.raises(MemoryAccessDeniedError):
            await manager.retrieve_memory(memory_id, scope=forbidden)
    finally:
        await manager.shutdown()


@pytest.mark.asyncio
async def test_search_memories_filters_out_of_scope_results():
    manager = MemoryManager()
    manager._initialized = True

    alice_item = MemoryItem.from_text("note one")
    alice_item.metadata.user_id = "alice"
    bob_item = MemoryItem.from_text("note two")
    bob_item.metadata.user_id = "bob"

    class FakeTier:
        async def search(self, *args, **kwargs):
            return SimpleNamespace(
                results=[
                    SimpleNamespace(memory=alice_item, relevance=0.9),
                    SimpleNamespace(memory=bob_item, relevance=0.8),
                ]
            )

    fake_tier = FakeTier()
    manager._get_tier_by_name = MagicMock(return_value=fake_tier)

    scope = MemoryRetrievalScope.for_user("alice")
    results = await manager.search_memories(scope=scope)
    assert results
    assert all(res["metadata"]["user_id"] == "alice" for res in results)

    admin_scope = MemoryRetrievalScope.for_user(
        "admin",
        roles=["admin"],
        allow_admin=True,
    )
    admin_results = await manager.search_memories(scope=admin_scope)
    assert {res["metadata"]["user_id"] for res in admin_results} == {"alice", "bob"}
