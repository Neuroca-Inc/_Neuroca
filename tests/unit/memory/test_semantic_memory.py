"""Unit tests for the in-memory semantic knowledge store."""

from __future__ import annotations

import pytest

from neuroca.memory.semantic_memory import Concept, RelationshipType, SemanticMemory


@pytest.fixture()
def semantic_memory() -> SemanticMemory:
    """Provide a fresh semantic memory instance for each test."""

    return SemanticMemory()


def test_store_and_retrieve_concepts(semantic_memory: SemanticMemory) -> None:
    concept_a = Concept(id="concept_a", name="Alpha")
    concept_b = Concept(id="concept_b", name="Beta")

    returned_a = semantic_memory.store(concept_a)
    returned_b = semantic_memory.store({"id": "concept_b", "name": "Beta"})

    assert returned_a == "concept_a"
    assert returned_b == "concept_b"
    assert semantic_memory.get_concept("concept_a") == concept_a
    assert semantic_memory.get_concept("concept_b") is not None


def test_store_relationships_requires_existing_concepts(
    semantic_memory: SemanticMemory,
) -> None:
    semantic_memory.store({"id": "concept_a", "name": "Alpha"})
    semantic_memory.store({"id": "concept_b", "name": "Beta"})

    rel_id = semantic_memory.store(
        {
            "source_id": "concept_a",
            "target_id": "concept_b",
            "relationship_type": RelationshipType.RELATED_TO,
            "metadata": {"weight": 0.8},
        }
    )

    relationships = semantic_memory.retrieve_relationships_for_concept("concept_a")
    assert len(relationships) == 1
    relationship = relationships[0]
    assert relationship.id == rel_id
    assert relationship.relationship_type == RelationshipType.RELATED_TO.value
    assert relationship.metadata == {"weight": 0.8}


def test_forget_concept_removes_relationships(semantic_memory: SemanticMemory) -> None:
    semantic_memory.store({"id": "concept_a", "name": "Alpha"})
    semantic_memory.store({"id": "concept_b", "name": "Beta"})
    semantic_memory.store({"source_id": "concept_a", "target_id": "concept_b"})

    removed = semantic_memory.forget_concept("concept_a")
    assert removed is True
    assert semantic_memory.get_concept("concept_a") is None
    assert semantic_memory.retrieve_relationships_for_concept("concept_b") == []


def test_get_metrics_reports_connectivity(semantic_memory: SemanticMemory) -> None:
    semantic_memory.store({"id": "concept_a", "name": "Alpha"})
    semantic_memory.store({"id": "concept_b", "name": "Beta"})
    semantic_memory.store({"source_id": "concept_a", "target_id": "concept_b"})

    metrics = semantic_memory.get_metrics()
    assert metrics["total_concepts"] == 2
    assert metrics["total_relationships"] == 1
    assert metrics["connectivity_ratio"] == pytest.approx(1.0)


def test_store_rejects_invalid_items(semantic_memory: SemanticMemory) -> None:
    with pytest.raises(ValueError):
        semantic_memory.store(object())  # type: ignore[arg-type]

