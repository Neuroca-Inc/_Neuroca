import pytest

from neuroca.core.enums import MemoryTier
from neuroca.memory.backends.factory import BackendType
from neuroca.memory.factory import create_memory_system
from neuroca.memory.models.memory_item import MemoryContent, MemoryItem, MemoryMetadata


@pytest.mark.asyncio
async def test_vector_search_returns_semantic_results(tmp_path):
    manager = create_memory_system(
        config={
            "backend_types": {
                "stm": BackendType.MEMORY.value,
                "mtm": BackendType.MEMORY.value,
                "ltm": BackendType.VECTOR.value,
            },
            "ltm": {
                "storage": {
                    "index_path": str(tmp_path / "integration-vector-index.json"),
                    "dimension": 3,
                }
            },
        }
    )

    await manager.initialize()
    try:
        embedding = [0.1, 0.2, 0.3]
        memory = MemoryItem(
            content=MemoryContent(text="Vector integration memory", summary="vector summary"),
            metadata=MemoryMetadata(tags={"integration": True}, tier=MemoryTier.LTM.storage_key),
            embedding=embedding,
            summary="vector summary",
        )
        memory_id = memory.id
        await manager.ltm_storage.store(memory.model_dump())

        results = await manager.search_memories(
            embedding=embedding,
            tiers=[MemoryTier.LTM.storage_key],
            limit=1,
        )

        assert results, "Vector search should yield at least one result"
        top_result = results[0]
        assert top_result["id"] == memory_id
        assert top_result["tier"] == MemoryTier.LTM.storage_key
        assert top_result["metadata"]["tags"]["integration"] is True
    finally:
        await manager.shutdown()
