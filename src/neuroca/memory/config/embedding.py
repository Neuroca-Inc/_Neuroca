"""Utility helpers for embedding configuration normalization."""

from __future__ import annotations

from typing import Any, Iterable, Mapping, MutableMapping

from neuroca.config.settings import get_settings
from neuroca.memory.exceptions import ConfigurationError


DEFAULT_EMBEDDING_DIMENSION = 1536


def _coerce_int(value: Any, *, source: str) -> int:
    try:
        dimension = int(value)
    except (TypeError, ValueError) as error:  # pragma: no cover - defensive guard
        raise ConfigurationError(
            f"Embedding dimension from {source} must be an integer value"
        ) from error

    if dimension <= 0:
        raise ConfigurationError(
            f"Embedding dimension from {source} must be greater than zero"
        )

    return dimension


def _extract_candidates(data: Mapping[str, Any] | None, keys: Iterable[tuple[str, ...]]) -> list[int]:
    if not isinstance(data, Mapping):
        return []

    values: list[int] = []
    for path in keys:
        current: Any = data
        for key in path:
            if not isinstance(current, Mapping) or key not in current:
                current = None
                break
            current = current[key]

        if current is not None:
            values.append(_coerce_int(current, source=" -> ".join(path)))

    return values


def resolve_embedding_dimension(
    *,
    explicit_override: int | None = None,
    manager_config: Mapping[str, Any] | None = None,
    settings_config: Mapping[str, Any] | None = None,
) -> int:
    """Return a validated embedding dimension for the memory system."""

    candidate_sources: list[tuple[str, int]] = []

    if explicit_override is not None:
        candidate_sources.append(
            (
                "factory override",
                _coerce_int(explicit_override, source="factory override"),
            )
        )

    if isinstance(manager_config, Mapping):
        for source, value in (
            ("config.embedding_dimension", manager_config.get("embedding_dimension")),
            ("config.embedding_dimensions", manager_config.get("embedding_dimensions")),
        ):
            if value is not None:
                candidate_sources.append((source, _coerce_int(value, source=source)))

        nested_candidates = _extract_candidates(
            manager_config,
            (
                ("ltm", "embedding_dimension"),
                ("ltm", "embedding_dimensions"),
                ("ltm", "storage", "dimension"),
                ("storage", "dimension"),
            ),
        )
        for dimension in nested_candidates:
            candidate_sources.append(("ltm configuration", dimension))

    settings_mapping: Mapping[str, Any] | None = settings_config
    if not isinstance(settings_mapping, Mapping):
        try:
            settings_mapping = get_settings().MEMORY_SYSTEM.model_dump()  # type: ignore[attr-defined]
        except Exception:  # pragma: no cover - defensive fallback
            settings_mapping = None

    settings_candidates: list[tuple[str, int]] = []
    if isinstance(settings_mapping, Mapping):
        extracted_settings = _extract_candidates(
            settings_mapping,
            (
                ("LONG_TERM_MEMORY", "EMBEDDING_DIMENSIONS"),
                ("LONG_TERM_MEMORY", "EMBEDDING_DIMENSION"),
                ("long_term_memory", "embedding_dimensions"),
                ("long_term_memory", "embedding_dimension"),
            ),
        )
        settings_candidates = [
            (
                "settings.long_term_memory.embedding_dimensions",
                dimension,
            )
            for dimension in extracted_settings
        ]

    include_settings = any(
        value != DEFAULT_EMBEDDING_DIMENSION for _, value in settings_candidates
    )
    if candidate_sources:
        if include_settings:
            candidate_sources.extend(settings_candidates)
    elif settings_candidates:
        candidate_sources.extend(settings_candidates)

    unique_values = {value for _, value in candidate_sources}
    if len(unique_values) > 1:
        details = ", ".join(f"{source}={value}" for source, value in candidate_sources)
        raise ConfigurationError(
            "Conflicting embedding dimension configuration detected: " + details
        )

    if unique_values:
        return unique_values.pop()

    if settings_candidates:
        # No conflicting overrides were provided, so fall back to the settings-derived value.
        return settings_candidates[0][1]

    return DEFAULT_EMBEDDING_DIMENSION


def ensure_embedding_dimension_fields(
    config: MutableMapping[str, Any],
    *,
    dimension: int,
) -> None:
    """Mutate *config* so all LTM embedding fields align to *dimension*."""

    ltm_section = config.setdefault("ltm", {})
    if isinstance(ltm_section, MutableMapping):
        ltm_section.setdefault("embedding_dimension", dimension)
        if "embedding_dimensions" in ltm_section:
            ltm_section["embedding_dimensions"] = dimension

        storage_section = ltm_section.setdefault("storage", {})
        if isinstance(storage_section, MutableMapping):
            storage_section.setdefault("dimension", dimension)

