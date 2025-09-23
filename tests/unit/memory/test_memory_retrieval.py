"""Unit tests covering the legacy memory retrieval façade."""

from __future__ import annotations

from datetime import datetime

import pytest

from neuroca.memory.episodic_memory import EpisodicMemory
from neuroca.memory.memory_retrieval import MemoryRetrieval
from neuroca.memory.semantic_memory import SemanticMemory
from neuroca.memory.working_memory import WorkingMemory


def _build_retrieval() -> MemoryRetrieval:
    """Create a retrieval helper populated with tier instances."""

    working = WorkingMemory()
    episodic = EpisodicMemory()
    semantic = SemanticMemory()
    return MemoryRetrieval(
        working_memory=working,
        episodic_memory=episodic,
        semantic_memory=semantic,
    )


def test_search_returns_results_across_all_tiers() -> None:
    """Retrieval should surface matches from working, episodic, and semantic tiers."""

    retrieval = _build_retrieval()

    working_id = retrieval.working_memory.store(  # type: ignore[union-attr]
        "Project Apollo planning session",  # pragma: no branch - helper always present
        tags={"project": True},
    )
    retrieval.episodic_memory.store(  # type: ignore[union-attr]
        {"text": "Met with the Apollo team to review project milestones."},
        emotional_salience=0.9,
        metadata={"timestamp": datetime.now().timestamp(), "tags": {"project": True}},
    )
    retrieval.semantic_memory.store(  # type: ignore[union-attr]
        {
            "name": "Project Apollo",
            "description": "Historical mission planning documents",
            "properties": {"category": "research"},
        }
    )

    results = retrieval.search("project", tiers=["working", "episodic", "semantic"], limit=5)

    tiers = {result.tier for result in results}
    assert {"working", "episodic", "semantic"}.issubset(tiers)

    working_result = next(result for result in results if result.tier == "working")
    assert working_result.memory_id == working_id
    assert "Apollo" in working_result.content["text"]


def test_threshold_filters_low_relevance_results() -> None:
    """Threshold should filter out memories whose relevance falls below the limit."""

    retrieval = _build_retrieval()

    retrieval.working_memory.store(  # type: ignore[union-attr]
        "High priority reminder",
        activation=0.9,
    )
    retrieval.working_memory.store(  # type: ignore[union-attr]
        "Low priority reminder",
        activation=0.2,
    )

    results = retrieval.search("reminder", tiers=["working"], threshold=0.5)

    assert len(results) == 1
    assert results[0].tier == "working"
    assert "High" in results[0].content["text"]


@pytest.mark.parametrize(
    "filters,expected",
    [
        ({"metadata": {"project": "apollo"}}, {"apollo"}),
        ({"tags": ["project"]}, {"apollo"}),
    ],
)
def test_metadata_filters_apply_to_retrieval_results(filters: dict[str, object], expected: set[str]) -> None:
    """Metadata filters should restrict results to matching memories."""

    retrieval = _build_retrieval()

    retrieval.working_memory.store(  # type: ignore[union-attr]
        "Apollo design discussion",
        project="apollo",
        tags={"project": True},
    )
    retrieval.working_memory.store(  # type: ignore[union-attr]
        "Gemini design discussion",
        project="gemini",
        tags={"topic": True},
    )

    results = retrieval.search({"query": "design", **filters}, tiers=["working"], limit=5)

    projects = {result.metadata.get("project") for result in results}
    assert projects == expected
    assert all(result.memory_type == "working" for result in results)
    assert all(isinstance(result.timestamp, datetime) for result in results)
