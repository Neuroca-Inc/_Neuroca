"""Unit tests for neuroca.memory.manager.utils helper functions."""

from types import SimpleNamespace

import pytest

from neuroca.memory.backends import MemoryTier
from neuroca.memory.manager.utils import (
    calculate_text_relevance,
    normalize_memory_format,
    truncate_text,
)
from neuroca.memory.models.memory_item import MemoryContent, MemoryItem, MemoryMetadata


def test_normalize_memory_format_stm_enriches_content_when_missing_text():
    """Ensure STM dictionaries receive synthesized content and identifiers."""
    memory = {
        "id": "stm-1",
        "data": {"text": "hello world"},
    }

    normalized = normalize_memory_format(memory, MemoryTier.STM)

    assert normalized["tier"] == MemoryTier.STM.value
    assert normalized["id"] == "stm-1"
    assert normalized["content"]["text"] == "hello world"


def test_normalize_memory_format_stm_uses_content_dict_when_present():
    """Existing STM content dictionaries should be reused without mutation."""
    memory = {"id": "stm-2", "content_dict": {"text": "prebuilt"}}

    normalized = normalize_memory_format(memory, MemoryTier.STM)

    assert normalized["content"]["text"] == "prebuilt"


def test_normalize_memory_format_stm_prefers_content_field():
    """STM payloads with content should surface that structure directly."""
    memory = {"id": "stm-3", "content": {"text": "preferred"}}

    normalized = normalize_memory_format(memory, MemoryTier.STM)

    assert normalized["content"]["text"] == "preferred"


def test_normalize_memory_format_stm_uses_text_key_when_available():
    """Top-level text fields should map into the synthetic content block."""
    memory = {"id": "stm-4", "text": "direct text"}

    normalized = normalize_memory_format(memory, MemoryTier.STM)

    assert normalized["content"]["text"] == "direct text"


def test_normalize_memory_format_stm_populates_proxy_content():
    """Dictionary-like objects can provide virtual content dictionaries."""

    class ContentProxy(dict):
        def get(self, key, default=None):  # type: ignore[override]
            if key == "content":
                return {"text": "proxy"}
            return super().get(key, default)

    proxy = ContentProxy(id="stm-5")

    normalized = normalize_memory_format(proxy, MemoryTier.STM)

    assert normalized["content"]["text"] == "proxy"


def test_normalize_memory_format_mtm_extracts_metadata_fields():
    """MTM objects should expose core attributes in the normalized payload."""
    mtm_object = SimpleNamespace(
        id="mtm-1",
        content={"text": "context"},
        created_at="2024-01-01T00:00:00Z",
        last_accessed="2024-01-02T00:00:00Z",
        access_count=5,
        priority=SimpleNamespace(value="high"),
        status="active",
        tags=["urgent"],
        metadata={"importance": 0.9},
    )

    normalized = normalize_memory_format(mtm_object, MemoryTier.MTM)

    assert normalized["id"] == "mtm-1"
    assert normalized["importance"] == 0.9
    assert normalized["priority"] == "high"
    assert normalized["tags"] == ["urgent"]


def test_normalize_memory_format_ltm_uses_memory_item_metadata():
    """LTM MemoryItem instances should round-trip metadata fields."""
    item = MemoryItem(
        content=MemoryContent(text="stored"),
        metadata=MemoryMetadata(importance=0.7, tags={"topic": "focus"}),
        summary="condensed",
    )

    normalized = normalize_memory_format(item, MemoryTier.LTM)

    assert normalized["id"] == item.id
    assert normalized["summary"] == "condensed"
    assert normalized["metadata"]["tags"] == {"topic": "focus"}
    assert normalized["importance"] == pytest.approx(0.7)


def test_normalize_memory_format_ltm_handles_attribute_metadata_object():
    """Metadata objects without dict() should still expose their key properties."""

    class DummyMetadata:
        def __init__(self) -> None:
            self.status = SimpleNamespace(value="archived")
            self.tags = ["doc"]
            self.importance = 0.2
            self.created_at = "2024-01-01"

    item = SimpleNamespace(
        id="ltm-dummy",
        content={"text": "body"},
        summary="summary", 
        metadata=DummyMetadata(),
    )

    normalized = normalize_memory_format(item, MemoryTier.LTM)

    assert normalized["status"] == "archived"
    assert normalized["tags"] == ["doc"]
    assert normalized["importance"] == pytest.approx(0.2)
    assert normalized["created_at"] == "2024-01-01"


def test_normalize_memory_format_handles_unknown_tier_gracefully():
    """Non-standard tiers should return the original mapping with tier metadata."""
    unknown_tier = SimpleNamespace(value="experimental")
    normalized = normalize_memory_format({"id": "raw"}, unknown_tier)  # type: ignore[arg-type]

    assert normalized == {"tier": "experimental"}


@pytest.mark.parametrize(
    "query, memory, expected",
    [
        ("focus topic", {"content": {"text": "A focus topic appears"}}, pytest.approx(0.75, rel=0.01)),
        ("missing", {"content": {"text": "no overlap"}}, 0.0),
        ("", {"content": {"text": "anything"}}, 0.0),
    ],
)
def test_calculate_text_relevance_handles_various_inputs(query, memory, expected):
    """The relevance helper should gracefully score diverse inputs."""
    score = calculate_text_relevance(query, memory)
    assert score == expected


def test_calculate_text_relevance_supports_object_with_summary():
    """Objects exposing content and summary should be merged before scoring."""
    memory = SimpleNamespace(content={"text": "Primary"}, summary="Secondary context")

    score = calculate_text_relevance("primary secondary", memory)

    assert score > 0.5


def test_calculate_text_relevance_handles_non_dict_content():
    """Stringifying non-dictionary content should still produce a relevance score."""
    memory = {"content": ["list", "data"], "summary": "list data"}

    score = calculate_text_relevance("list data", memory)

    assert score > 0.0


def test_calculate_text_relevance_handles_dict_without_text_key():
    """Dictionaries without text keys should be stringified for comparison."""
    memory = {"content": {"raw": "value"}}

    score = calculate_text_relevance("value", memory)

    assert score == 0.0


def test_calculate_text_relevance_falls_back_to_string_representation():
    """Objects without content should fall back to their string form."""
    score = calculate_text_relevance("object", object())

    assert score >= 0.0


def test_calculate_text_relevance_handles_object_content_without_dict():
    """Objects exposing scalar content should be coerced to strings."""
    memory = SimpleNamespace(content="Scalar", summary=None)

    score = calculate_text_relevance("scalar", memory)

    assert score > 0.0


def test_calculate_text_relevance_handles_object_dict_without_text():
    """Object-backed dictionaries without text should stringify the payload."""
    memory = SimpleNamespace(content={"extra": "value"}, summary=None)

    score = calculate_text_relevance("value", memory)

    assert score == 0.0


def test_calculate_text_relevance_returns_zero_for_empty_memory_words():
    """Whitespace queries with empty memory tokens should return zero overlap."""
    memory = {"content": ""}

    score = calculate_text_relevance(" ", memory)

    assert score == 0.0


def test_truncate_text_limits_token_count_and_appends_ellipsis():
    """Truncation should respect the requested token budget."""
    text = "one two three four five"

    assert truncate_text(text, 10) == text
    assert truncate_text(text, 2) == "one two..."
