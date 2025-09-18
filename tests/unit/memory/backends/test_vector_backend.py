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


@pytest.mark.asyncio
async def test_vector_backend_integrity_checks_flag_and_fix_drift(tmp_path):
    backend = StorageBackendFactory.create_storage(
        tier=MemoryTier.LTM,
        backend_type=BackendType.VECTOR,
        config={"index_path": str(tmp_path / "vector-index.json"), "dimension": 3},
        use_existing=False,
        instance_name="vector_integrity_backend",
    )

    await backend.initialize()

    memory = MemoryItem(
        id="vector-memory",
        content={"text": "vector storage test"},
        metadata=MemoryMetadata(tags={"topic": True}, tier="ltm"),
        embedding=[0.1, 0.2, 0.3],
        summary="vector storage test",
    )

    await backend.store(memory)

    # Simulate drift by updating the stored payload without touching the index entry.
    metadata = backend.storage.get_memory_metadata(memory.id)
    drifted_embedding = [0.8, 0.1, 0.1]
    metadata.setdefault("memory", memory.model_dump(mode="json"))
    metadata["memory"]["embedding"] = drifted_embedding
    backend.storage.set_memory_metadata(memory.id, metadata)

    drift_report = await backend.check_index_integrity(drift_threshold=0.05)
    assert memory.id in drift_report.drifted_ids
    assert drift_report.drift_scores[memory.id] > 0.05

    repair_report = await backend.reindex(target_ids=[memory.id], drift_threshold=0.05)
    assert repair_report.reindexed is True
    assert repair_report.reindexed_entry_count == 1
    assert memory.id not in repair_report.drifted_ids

    entry = backend.index.get(memory.id)
    assert entry is not None
    assert entry.vector == drifted_embedding

    await backend.shutdown()


@pytest.mark.asyncio
async def test_embedding_model_swap_plan_and_commit(tmp_path):
    backend = StorageBackendFactory.create_storage(
        tier=MemoryTier.LTM,
        backend_type=BackendType.VECTOR,
        config={"index_path": str(tmp_path / "vector-index.json"), "dimension": 3},
        use_existing=False,
        instance_name="vector_model_swap_backend",
    )

    await backend.initialize()

    base_memories = [
        MemoryItem(
            id=f"memory-{index}",
            content={"text": f"memory {index}"},
            metadata=MemoryMetadata(tags={"topic": "swap"}, tier="ltm"),
            embedding=[0.1 * (index + 1), 0.2 * (index + 1), 0.3 * (index + 1)],
            summary=f"memory {index}",
        )
        for index in range(2)
    ]

    for memory in base_memories:
        await backend.store(memory)

    def embedder(batch):
        embeddings = []
        for item in batch:
            source = item.embedding or [0.0, 0.0, 0.0]
            embeddings.append([value + 0.01 for value in source])
        return embeddings

    plan = await backend.plan_embedding_model_swap(
        target_model="new-embedding-model",
        embedder=embedder,
        drift_threshold=0.5,
    )

    assert plan.ready is True
    assert plan.commit_allowed is True
    assert plan.target_dimension == 3
    assert len(plan.staged_ids()) == len(base_memories)

    await backend.execute_embedding_model_swap(plan)
    assert plan.committed is True

    for memory in base_memories:
        updated = await backend.retrieve(memory.id)
        assert updated is not None
        assert updated.metadata.embedding_model == "new-embedding-model"
        assert updated.metadata.embedding_dimensions == 3
        assert updated.embedding not in (memory.embedding or [])

        index_entry = backend.index.get(memory.id)
        assert index_entry is not None
        assert index_entry.vector == updated.embedding

    await backend.shutdown()


@pytest.mark.asyncio
async def test_embedding_model_swap_blocks_dimension_mismatch(tmp_path):
    backend = StorageBackendFactory.create_storage(
        tier=MemoryTier.LTM,
        backend_type=BackendType.VECTOR,
        config={"index_path": str(tmp_path / "vector-index.json"), "dimension": 3},
        use_existing=False,
        instance_name="vector_model_swap_mismatch",
    )

    await backend.initialize()

    memory = MemoryItem(
        id="dimension-memory",
        content={"text": "dimension check"},
        metadata=MemoryMetadata(tags={"topic": "swap"}, tier="ltm"),
        embedding=[0.1, 0.2, 0.3],
        summary="dimension check",
    )

    await backend.store(memory)

    def bad_embedder(batch):
        return [[0.5, 0.6] for _ in batch]

    plan = await backend.plan_embedding_model_swap(
        target_model="invalid",
        embedder=bad_embedder,
        expected_dimension=3,
    )

    assert plan.ready is False
    assert plan.commit_allowed is False
    assert memory.id in plan.dimension_mismatch_ids

    with pytest.raises(ValueError):
        await backend.execute_embedding_model_swap(plan)

    await backend.shutdown()


@pytest.mark.asyncio
async def test_embedding_model_swap_requires_full_coverage_for_commit(tmp_path):
    backend = StorageBackendFactory.create_storage(
        tier=MemoryTier.LTM,
        backend_type=BackendType.VECTOR,
        config={"index_path": str(tmp_path / "vector-index.json"), "dimension": 3},
        use_existing=False,
        instance_name="vector_model_swap_sample",
    )

    await backend.initialize()

    for index in range(3):
        await backend.store(
            MemoryItem(
                id=f"sampled-{index}",
                content={"text": f"sample {index}"},
                metadata=MemoryMetadata(tags={"topic": "swap"}, tier="ltm"),
                embedding=[0.1 * (index + 1)] * 3,
                summary=f"sample {index}",
            )
        )

    def embedder(batch):
        return [
            [(value + 0.02) for value in (item.embedding or [0.0, 0.0, 0.0])]
            for item in batch
        ]

    plan = await backend.plan_embedding_model_swap(
        target_model="new-embedding-model",
        embedder=embedder,
        sample_size=1,
        drift_threshold=0.5,
    )

    assert plan.ready is True
    assert plan.commit_allowed is False
    assert any("subset" in warning for warning in plan.warnings)
    assert len(plan.staged_ids()) == 1

    await backend.shutdown()
