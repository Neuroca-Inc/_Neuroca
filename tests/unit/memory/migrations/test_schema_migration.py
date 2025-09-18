from __future__ import annotations

import pytest

from neuroca.memory.migrations import (
    adjust_embedding_dimension,
    ensure_summarization_package,
)
from neuroca.memory.models.memory_item import MemoryItem


def build_memory(**overrides: object) -> MemoryItem:
    base = {
        "id": "memory-1",
        "content": {"text": "System log entry", "summary": "Log summary"},
        "metadata": {
            "additional_metadata": {},
        },
        "summary": None,
        "embedding": [0.1, 0.2, 0.3, 0.4],
    }
    base.update(overrides)
    return MemoryItem.model_validate(base)


def test_ensure_summarization_package_converts_legacy_fields() -> None:
    memory = build_memory(
        metadata={
            "additional_metadata": {
                "summary_text": "Incident resolved after failover",
                "summary_keywords": ["incident", "failover"],
                "summary_highlights": [
                    "Failover triggered at 12:04",
                    "Load normalised after redirect",
                ],
                "summary_metadata": {"source": "legacy"},
            }
        }
    )

    changed = ensure_summarization_package(memory)

    assert changed is True
    summarisation = memory.metadata.additional_metadata.get("summarization")
    assert summarisation is not None
    assert summarisation["aggregated"] == "Incident resolved after failover"
    assert summarisation["keywords"] == ["incident", "failover"]
    assert summarisation["highlights"] == [
        "Failover triggered at 12:04",
        "Load normalised after redirect",
    ]
    assert summarisation["batch"] == {"source": "legacy"}
    assert "summary_text" not in memory.metadata.additional_metadata
    assert "summary_keywords" not in memory.metadata.additional_metadata


def test_ensure_summarization_package_populates_from_summary_field() -> None:
    memory = build_memory(summary="Consolidated summary text", metadata={"additional_metadata": {}})

    changed = ensure_summarization_package(memory)

    assert changed is True
    summarisation = memory.metadata.additional_metadata.get("summarization")
    assert summarisation["aggregated"] == "Consolidated summary text"
    assert summarisation["keywords"] == []
    assert summarisation["highlights"] == []


def test_ensure_summarization_package_is_noop_when_current() -> None:
    memory = build_memory(
        metadata={
            "additional_metadata": {
                "summarization": {
                    "aggregated": "Current summary",
                    "keywords": ["present"],
                    "highlights": ["Existing highlight"],
                    "batch": {"version": 2},
                }
            }
        }
    )

    changed = ensure_summarization_package(memory)

    assert changed is False
    summarisation = memory.metadata.additional_metadata["summarization"]
    assert summarisation["batch"] == {"version": 2}


@pytest.mark.parametrize("original, expected", [
    ([0.0, 0.5, 1.0, 1.5, 2.0], [0.0, 0.5, 1.0]),
    ([0.0, 0.5], [0.0, 0.5, 0.0, 0.0]),
])
def test_adjust_embedding_dimension_enforces_length(original: list[float], expected: list[float]) -> None:
    memory = build_memory(embedding=list(original), metadata={"additional_metadata": {}})

    changed = adjust_embedding_dimension(memory, len(expected))

    assert changed is True
    assert memory.embedding == pytest.approx(expected)
    assert memory.metadata.embedding_dimensions == len(expected)


def test_adjust_embedding_dimension_noop_without_embedding() -> None:
    memory = build_memory(embedding=None)

    changed = adjust_embedding_dimension(memory, 5)

    assert changed is False
    assert memory.embedding is None
