import pytest

from neuroca.memory.backends.factory import BackendType, MemoryTier, StorageBackendFactory
from neuroca.memory.models.memory_item import MemoryItem, MemoryMetadata


@pytest.mark.asyncio
async def test_vector_backend_registers_and_handles_core_flows(tmp_path):
    backend = StorageBackendFactory.create_storage(
        tier=MemoryTier.LTM,
        backend_type=BackendType.VECTOR,
        config={"index_path": str(tmp_path / "vector-index.json"), "dimension": 3},
        use_existing=False,
        instance_name="test_vector_backend",
    )

    await backend.initialize()

    memory = MemoryItem(
        id="vector-memory",
        content={"text": "vector storage test"},
        metadata=MemoryMetadata(tags={"topic": True}, tier="ltm"),
        embedding=[0.1, 0.2, 0.3],
        summary="vector storage test",
    )

    stored_id = await backend.store(memory)
    assert stored_id == "vector-memory"

    stored_payload = await backend.read(memory.id)
    assert stored_payload is not None
    assert stored_payload["metadata"]["tier"] == "ltm"

    query_results = await backend.query(filters={"metadata.tier": "ltm"}, limit=5, offset=0)
    assert any(result["id"] == memory.id for result in query_results)

    search_results = await backend.similarity_search(
        embedding=memory.embedding,
        filters={"metadata.tier": "ltm", "metadata.status": "active"},
        limit=5,
        offset=0,
    )
    assert len(search_results) == 1
    assert search_results[0]["id"] == memory.id
    assert search_results[0]["metadata"].get("relevance") is not None

    assert await backend.delete(memory.id) is True
    assert await backend.read(memory.id) is None

    await backend.shutdown()
