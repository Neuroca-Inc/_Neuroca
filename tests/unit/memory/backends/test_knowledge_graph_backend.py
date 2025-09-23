"""Unit tests for the in-memory knowledge graph backend."""

import pytest

from neuroca.memory.backends.knowledge_graph import InMemoryKnowledgeGraphBackend


@pytest.mark.asyncio
async def test_add_and_query_relationships() -> None:
    backend = InMemoryKnowledgeGraphBackend()

    await backend.add_relationship(
        "source",
        "target",
        "semantic",
        strength=0.9,
        metadata={"weight": 1},
    )
    await backend.add_relationship(
        "source",
        "alt",
        "causal",
        strength=0.4,
        metadata=None,
    )

    related = await backend.get_related("source", relationship_type="semantic", min_strength=0.5)
    assert related == [
        {
            "relationship_type": "semantic",
            "target_id": "target",
            "strength": 0.9,
            "metadata": {"weight": 1},
        }
    ]


@pytest.mark.asyncio
async def test_remove_relationship_and_node_cleanup() -> None:
    backend = InMemoryKnowledgeGraphBackend()

    await backend.add_relationship("a", "b", "semantic", strength=0.8)
    await backend.add_relationship("b", "a", "semantic", strength=0.8)

    removed = await backend.remove_relationship("a", "b")
    assert removed is True
    assert await backend.get_related("a") == []

    await backend.remove_node("b")
    assert await backend.get_related("b") == []
