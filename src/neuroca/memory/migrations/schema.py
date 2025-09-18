"""Utilities for migrating memory schema fields."""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence

from neuroca.memory.models.memory_item import MemoryContent, MemoryItem

_LEGACY_AGGREGATE_KEYS = {
    "summary_text",
    "summary_body",
    "summary_content",
    "summary_sentence",
    "summary_blob",
}
_LEGACY_KEYWORD_KEYS = {"summary_keywords"}
_LEGACY_HIGHLIGHT_KEYS = {"summary_highlights"}
_LEGACY_BATCH_KEYS = {"summary_metadata", "summary_batch_metadata"}
_LEGACY_BUNDLE_KEYS = {"summary_bundle", "summary_package"}


def _coerce_text(value: Any) -> str:
    """Return a normalised text representation for summary fields."""

    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (bytes, bytearray)):
        try:
            return value.decode().strip()
        except Exception:  # pragma: no cover - defensive conversion
            return ""
    if isinstance(value, (int, float, bool)):
        return str(value)
    return ""


def _coerce_string_list(value: Any) -> list[str]:
    """Best-effort conversion of arbitrary values into a list of strings."""

    if value is None:
        return []
    if isinstance(value, str):
        candidate = _coerce_text(value)
        return [candidate] if candidate else []
    if isinstance(value, Mapping):
        return [
            text
            for text in (_coerce_text(item) for item in value.values())
            if text
        ]
    result: list[str] = []
    if isinstance(value, Iterable):
        for item in value:
            text = _coerce_text(item)
            if text:
                result.append(text)
        return result
    text = _coerce_text(value)
    return [text] if text else []


def _merge_unique_strings(values: Sequence[Sequence[str]]) -> list[str]:
    """Merge multiple string sequences while preserving original order."""

    seen: set[str] = set()
    merged: list[str] = []
    for sequence in values:
        for item in sequence:
            if item in seen:
                continue
            seen.add(item)
            merged.append(item)
    return merged


def _normalise_existing_package(value: Mapping[str, Any] | None) -> dict[str, Any] | None:
    """Return a normalised summarisation package when already present."""

    if not isinstance(value, Mapping):
        return None

    aggregated = _coerce_text(value.get("aggregated") or value.get("summary"))
    keywords = _coerce_string_list(value.get("keywords"))
    highlights = _coerce_string_list(value.get("highlights"))

    batch_raw = value.get("batch") or value.get("metadata")
    batch = dict(batch_raw) if isinstance(batch_raw, Mapping) else {}

    return {
        "aggregated": aggregated,
        "keywords": keywords,
        "highlights": highlights,
        "batch": batch,
    }


def _extract_from_bundle(bundle: Mapping[str, Any]) -> tuple[str, list[str], list[str], dict[str, Any]]:
    """Extract summarisation fields from a legacy bundle payload."""

    aggregated = _coerce_text(
        bundle.get("aggregated")
        or bundle.get("summary")
        or bundle.get("text")
    )
    keywords = _coerce_string_list(bundle.get("keywords"))
    highlights = _coerce_string_list(bundle.get("highlights"))
    batch_raw = bundle.get("batch") or bundle.get("metadata")
    batch = dict(batch_raw) if isinstance(batch_raw, Mapping) else {}
    return aggregated, keywords, highlights, batch


def ensure_summarization_package(memory: MemoryItem) -> bool:
    """Upgrade legacy summary metadata to the consolidated package structure."""

    metadata = memory.metadata
    if metadata is None:
        return False

    additional_raw = metadata.additional_metadata or {}
    additional: dict[str, Any] = dict(additional_raw)

    existing_package = _normalise_existing_package(additional.get("summarization"))
    package_requires_normalisation = existing_package is None
    if existing_package is None:
        existing_package = {
            "aggregated": "",
            "keywords": [],
            "highlights": [],
            "batch": {},
        }

    legacy_aggregated: list[str] = []
    legacy_keywords: list[list[str]] = []
    legacy_highlights: list[list[str]] = []
    legacy_batch: list[Mapping[str, Any]] = []
    removed_legacy_keys = False

    for key in list(additional.keys()):
        lower_key = key.lower()
        value = additional[key]
        if lower_key in _LEGACY_AGGREGATE_KEYS:
            legacy_aggregated.append(_coerce_text(value))
            removed_legacy_keys = True
            additional.pop(key)
            continue
        if lower_key in _LEGACY_KEYWORD_KEYS:
            legacy_keywords.append(_coerce_string_list(value))
            removed_legacy_keys = True
            additional.pop(key)
            continue
        if lower_key in _LEGACY_HIGHLIGHT_KEYS:
            legacy_highlights.append(_coerce_string_list(value))
            removed_legacy_keys = True
            additional.pop(key)
            continue
        if lower_key in _LEGACY_BATCH_KEYS:
            if isinstance(value, Mapping):
                legacy_batch.append(value)
            removed_legacy_keys = True
            additional.pop(key)
            continue
        if lower_key in _LEGACY_BUNDLE_KEYS and isinstance(value, Mapping):
            agg, kwds, hl, batch = _extract_from_bundle(value)
            if agg:
                legacy_aggregated.append(agg)
            if kwds:
                legacy_keywords.append(kwds)
            if hl:
                legacy_highlights.append(hl)
            if batch:
                legacy_batch.append(batch)
            removed_legacy_keys = True
            additional.pop(key)

    aggregated_candidates: list[str] = []
    aggregated_candidates.extend(text for text in legacy_aggregated if text)
    existing_aggregated = _coerce_text(existing_package.get("aggregated"))
    if existing_aggregated:
        aggregated_candidates.append(existing_aggregated)

    if memory.summary:
        aggregated_candidates.append(_coerce_text(memory.summary))

    content = memory.content
    if isinstance(content, MemoryContent):
        aggregated_candidates.append(_coerce_text(content.summary))
        aggregated_candidates.append(_coerce_text(content.text))
    elif isinstance(content, Mapping):
        aggregated_candidates.append(_coerce_text(content.get("summary")))
        aggregated_candidates.append(_coerce_text(content.get("text")))

    aggregated_text = next((text for text in aggregated_candidates if text), "")

    keyword_sequences: list[list[str]] = []
    keyword_sequences.extend(legacy_keywords)
    keyword_sequences.append(existing_package.get("keywords", []))
    keywords = _merge_unique_strings(keyword_sequences)

    highlight_sequences: list[list[str]] = []
    highlight_sequences.extend(legacy_highlights)
    highlight_sequences.append(existing_package.get("highlights", []))
    highlights = _merge_unique_strings(highlight_sequences)

    batch_entries: dict[str, Any] = {}
    for legacy_batch_entry in legacy_batch:
        batch_entries.update(legacy_batch_entry)
    existing_batch = existing_package.get("batch")
    if isinstance(existing_batch, Mapping):
        batch_entries.update(existing_batch)

    new_package = {
        "aggregated": aggregated_text,
        "keywords": keywords,
        "highlights": highlights,
        "batch": batch_entries,
    }

    if not package_requires_normalisation and not removed_legacy_keys:
        # Package already present; check if normalisation changes it.
        if new_package == existing_package:
            return False

    additional["summarization"] = new_package
    metadata.additional_metadata = additional
    memory.metadata = metadata
    return True


def adjust_embedding_dimension(memory: MemoryItem, target_dimension: int | None) -> bool:
    """Ensure embeddings conform to the specified dimension."""

    if not target_dimension or target_dimension <= 0:
        return False

    embedding = memory.embedding
    if embedding is None:
        return False

    vector = list(embedding)
    original_length = len(vector)
    if original_length == target_dimension:
        metadata = memory.metadata
        if metadata and metadata.embedding_dimensions != target_dimension:
            metadata.embedding_dimensions = target_dimension
            memory.metadata = metadata
            return True
        return False

    if original_length > target_dimension:
        vector = vector[:target_dimension]
    else:
        vector.extend([0.0] * (target_dimension - original_length))

    memory.embedding = vector
    metadata = memory.metadata
    if metadata:
        metadata.embedding_dimensions = target_dimension
        memory.metadata = metadata
    return True
