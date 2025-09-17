"""Regression tests for legacy MemoryManager compatibility shims."""

from unittest.mock import AsyncMock

import pytest

from neuroca.core.enums import MemoryTier
from neuroca.memory.manager import MemoryManager
from neuroca.memory.models.memory_item import MemoryContent, MemoryItem, MemoryMetadata


@pytest.fixture()
def configured_manager() -> MemoryManager:
    manager = MemoryManager()
    manager.add_memory = AsyncMock(return_value="legacy-id")
    manager.search_memories = AsyncMock()
    manager.retrieve_memory = AsyncMock()
    return manager


def test_store_maps_legacy_arguments(configured_manager: MemoryManager) -> None:
    result = configured_manager.store(
        content={"payload": "value"},
        summary="summary",
        memory_type="semantic",
        metadata={"origin": "test"},
        emotional_salience=0.8,
        tags=["semantic"],
        importance=0.9,
    )

    assert result == "legacy-id"
    configured_manager.add_memory.assert_awaited_once()
    kwargs = configured_manager.add_memory.await_args.kwargs
    assert kwargs["initial_tier"] == MemoryTier.SEMANTIC.storage_key
    assert kwargs["metadata"]["origin"] == "test"
    assert kwargs["metadata"]["emotional_salience"] == 0.8
    assert kwargs["importance"] == 0.9
    assert kwargs["tags"] == ["semantic"]


def test_retrieve_converts_search_results(configured_manager: MemoryManager) -> None:
    configured_manager.search_memories.return_value = [
        {
            "content": {"data": {"success": True, "reason": "test"}},
            "metadata": {"tier": "ltm", "relevance": 0.75},
            "_relevance": 0.75,
            "id": "abc-123",
        }
    ]

    results = configured_manager.retrieve(query="goal", memory_type=MemoryTier.SEMANTIC, limit=3)

    configured_manager.search_memories.assert_awaited_once()
    assert len(results) == 1
    record = results[0]
    assert record.content == {"success": True, "reason": "test"}
    assert record.metadata["tier"] == "ltm"
    assert record.relevance == 0.75
    assert record.id == "abc-123"


def test_retrieve_by_id_wraps_memory_item(configured_manager: MemoryManager) -> None:
    memory_item = MemoryItem(content=MemoryContent(text="hello"), metadata=MemoryMetadata())
    configured_manager.retrieve_memory.return_value = memory_item

    result = configured_manager.retrieve("item-42", tier="stm")

    configured_manager.retrieve_memory.assert_awaited_once_with("item-42", tier="stm")
    assert result.content == "hello"
    assert result.metadata["tier"] is None
