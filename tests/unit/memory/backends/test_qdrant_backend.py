"""Unit tests for the Qdrant vector backend."""

import pytest

from neuroca.memory.backends import BackendType, MemoryTier, StorageBackendFactory
from neuroca.memory.models.memory_item import MemoryItem, MemoryMetadata


@pytest.mark.asyncio
async def test_qdrant_backend_round_trip_preserves_relationships():
    """Verify that the Qdrant backend stores, retrieves, and filters knowledge graph metadata."""

    backend = StorageBackendFactory.create_storage(
        tier=MemoryTier.LTM,
        backend_type=BackendType.QDRANT,
        config={
            "location": ":memory:",
            "collection_name": "qdrant_backend_test",
            "dimension": 3,
            "recreate_collection": True,
        },
        use_existing=False,
        instance_name="qdrant_backend_test",
    )

    await backend.initialize()

    alpha = MemoryItem(
        id="concept-alpha",
        content={"text": "Alpha concept about graph theory."},
        metadata=MemoryMetadata(
            tier="ltm",
            tags={
                "concept": "alpha",
                "relationships": {
                    "related_to": ["concept-beta"],
                    "semantic_edge": {
                        "type": "related_to",
                        "weight": 0.85,
                    },
                },
            },
        ),
        summary="alpha summary",
        embedding=[0.05, 0.1, 0.2],
    )

    beta = MemoryItem(
        id="concept-beta",
        content={"text": "Beta node referencing Alpha."},
        metadata=MemoryMetadata(
            tier="ltm",
            tags={
                "concept": "beta",
                "relationships": {
                    "related_to": ["concept-alpha"],
                    "semantic_edge": {
                        "type": "related_to",
                        "weight": 0.9,
                    },
                },
            },
        ),
        summary="beta summary",
        embedding=[0.06, 0.11, 0.19],
    )

    created_ids = await backend.batch_store([alpha, beta])
    assert set(created_ids) == {alpha.id, beta.id}

    stored_alpha = await backend.retrieve(alpha.id)
    assert stored_alpha is not None
    assert stored_alpha.metadata.tags["relationships"]["related_to"] == [beta.id]

    tier_results = await backend.query(filters={"metadata.tags.concept": "alpha"})
    assert len(tier_results) == 1
    assert tier_results[0]["metadata"]["tags"]["concept"] == "alpha"

    search_results = await backend.similarity_search(
        embedding=alpha.embedding or [],
        filters={"metadata.tags.relationships.related_to": {"$any": [beta.id]}},
        limit=5,
    )
    assert search_results
    top_hit = search_results[0]
    assert top_hit["metadata"]["tags"]["relationships"]["semantic_edge"]["type"] == "related_to"
    assert "relevance" in top_hit["metadata"]

    count = await backend.count()
    assert count == 2

    assert await backend.delete(beta.id) is True
    assert await backend.count() == 1

    await backend.shutdown()
