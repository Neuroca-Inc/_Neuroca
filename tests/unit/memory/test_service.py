from unittest.mock import AsyncMock
from uuid import UUID

import pytest

from neuroca.core.enums import MemoryTier
from neuroca.core.exceptions import MemoryNotFoundError
from neuroca.memory.models.memory_item import MemoryItem
from neuroca.memory.service import MemoryResponse, MemorySearchParams, MemoryService


@pytest.mark.asyncio
async def test_create_memory_uses_async_manager():
    service = MemoryService()
    fake_item = MemoryItem.from_text("hello world")
    fake_item.metadata.tier = MemoryTier.STM.storage_key

    service.memory_manager = AsyncMock()
    service._initialized = True
    service.memory_manager.add_memory.return_value = "memory-id"
    service.memory_manager.retrieve_memory.return_value = fake_item

    payload = {
        "content": "hello world",
        "user_id": "user-123",
        "importance": 0.8,
        "tags": ["greeting"],
    }

    response = await service.create_memory(payload)

    service.memory_manager.add_memory.assert_awaited_once()
    service.memory_manager.retrieve_memory.assert_awaited_once_with("memory-id")
    assert isinstance(response, MemoryResponse)
    assert response.id == fake_item.id
    assert response.tier == MemoryTier.STM.storage_key


@pytest.mark.asyncio
async def test_list_memories_passes_filters():
    service = MemoryService()
    service.memory_manager = AsyncMock()
    service._initialized = True

    service.memory_manager.search_memories.return_value = [
        {
            "id": "abc",
            "content": {"text": "example"},
            "metadata": {"user_id": "user-1", "tier": MemoryTier.MTM.storage_key},
        }
    ]

    params = MemorySearchParams(user_id="user-1", query="example", tier="mtm", limit=5)
    results = await service.list_memories(params)

    assert len(results) == 1
    call_kwargs = service.memory_manager.search_memories.await_args.kwargs
    assert call_kwargs["metadata_filters"] == {"metadata.user_id": "user-1"}
    assert call_kwargs["tiers"] == [MemoryTier.MTM.storage_key]


@pytest.mark.asyncio
async def test_update_memory_returns_refreshed_item():
    service = MemoryService()
    service.memory_manager = AsyncMock()
    service._initialized = True

    updated_item = MemoryItem.from_text("updated")
    updated_item.metadata.tier = MemoryTier.LTM.storage_key

    service.memory_manager.update_memory.return_value = True
    service.memory_manager.retrieve_memory.return_value = updated_item

    response = await service.update_memory(UUID("12345678-1234-5678-1234-567812345678"), {"content": "updated"})

    service.memory_manager.update_memory.assert_awaited()
    service.memory_manager.retrieve_memory.assert_awaited()
    assert response.content["text"] == "updated"
    assert response.tier == MemoryTier.LTM.storage_key


@pytest.mark.asyncio
async def test_delete_memory_raises_for_missing_record():
    service = MemoryService()
    service.memory_manager = AsyncMock()
    service._initialized = True
    service.memory_manager.delete_memory.return_value = False

    with pytest.raises(MemoryNotFoundError):
        await service.delete_memory(UUID("12345678-1234-5678-1234-567812345678"))


@pytest.mark.asyncio
async def test_transfer_memory_normalizes_target_tier():
    service = MemoryService()
    service.memory_manager = AsyncMock()
    service._initialized = True
    transferred = MemoryItem.from_text("move me")
    transferred.metadata.tier = MemoryTier.MTM.storage_key
    service.memory_manager.transfer_memory.return_value = transferred

    response = await service.transfer_memory(UUID("12345678-1234-5678-1234-567812345678"), "mtm")

    service.memory_manager.transfer_memory.assert_awaited_once()
    assert response.tier == MemoryTier.MTM.storage_key
