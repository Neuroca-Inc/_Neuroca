"""Validation helpers for memory configuration inputs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from neuroca.memory.exceptions import ConfigurationError


def _as_mapping(value: Any) -> Mapping[str, Any] | None:
    return value if isinstance(value, Mapping) else None


def _resolve_key(mapping: Mapping[str, Any], key: str) -> Any:
    if key in mapping:
        return mapping[key]
    if isinstance(key, str):
        lowered = key.lower()
        for candidate, value in mapping.items():
            if isinstance(candidate, str) and candidate.lower() == lowered:
                return value
    return None


def _extract_nested(mapping: Mapping[str, Any], path: Sequence[str]) -> Any:
    current: Any = mapping
    for key in path:
        if not isinstance(current, Mapping):
            return None
        current = _resolve_key(current, key)
        if current is None:
            return None
    return current


def _coerce_float(value: Any, *, source: str) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError) as exc:
        raise ConfigurationError(
            f"{source} must be a numeric value, received {value!r}"
        ) from exc
    return numeric


def _is_non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and value.strip() != ""


@dataclass(frozen=True)
class _ThresholdSpec:
    name: str
    manager_paths: tuple[tuple[str, ...], ...]
    settings_paths: tuple[tuple[str, ...], ...]
    minimum: float | None = None
    maximum: float | None = None
    exclusive_minimum: bool = False
    exclusive_maximum: bool = False


_THRESHOLD_SPECS: tuple[_ThresholdSpec, ...] = (
    _ThresholdSpec(
        name="short-term consolidation threshold",
        manager_paths=(("stm", "consolidation_threshold"),),
        settings_paths=(
            ("short_term_memory", "consolidation_threshold"),
            ("SHORT_TERM_MEMORY", "CONSOLIDATION_THRESHOLD"),
        ),
        minimum=0.0,
        maximum=1.0,
        exclusive_minimum=True,
        exclusive_maximum=True,
    ),
    _ThresholdSpec(
        name="short-term retrieval boost",
        manager_paths=(("stm", "retrieval_boost"),),
        settings_paths=(
            ("short_term_memory", "retrieval_boost"),
            ("SHORT_TERM_MEMORY", "RETRIEVAL_BOOST"),
        ),
        minimum=0.0,
        maximum=1.0,
        exclusive_minimum=False,
        exclusive_maximum=True,
    ),
    _ThresholdSpec(
        name="long-term similarity threshold",
        manager_paths=(("ltm", "similarity_threshold"),),
        settings_paths=(
            ("long_term_memory", "similarity_threshold"),
            ("LONG_TERM_MEMORY", "SIMILARITY_THRESHOLD"),
        ),
        minimum=0.0,
        maximum=1.0,
        exclusive_minimum=True,
        exclusive_maximum=True,
    ),
)


_REQUIRED_SCHEMA_FIELDS = ("metadata_table", "content_table", "tags_table")


def _first_numeric(
    mapping: Mapping[str, Any] | None,
    paths: Sequence[tuple[str, ...]],
) -> tuple[float | None, tuple[str, ...] | None]:
    if not isinstance(mapping, Mapping):
        return None, None
    for path in paths:
        value = _extract_nested(mapping, path)
        if value is None:
            continue
        numeric = _coerce_float(value, source=" -> ".join(path))
        return numeric, path
    return None, None


def _assert_range(value: float, spec: _ThresholdSpec, *, source: str) -> None:
    if spec.minimum is not None:
        if spec.exclusive_minimum:
            if not value > spec.minimum:
                raise ConfigurationError(
                    f"{source} must be greater than {spec.minimum}, received {value}"
                )
        elif value < spec.minimum:
            raise ConfigurationError(
                f"{source} must be at least {spec.minimum}, received {value}"
            )

    if spec.maximum is not None:
        if spec.exclusive_maximum:
            if not value < spec.maximum:
                raise ConfigurationError(
                    f"{source} must be less than {spec.maximum}, received {value}"
                )
        elif value > spec.maximum:
            raise ConfigurationError(
                f"{source} must be at most {spec.maximum}, received {value}"
            )


def _validate_thresholds(
    manager_config: Mapping[str, Any] | None,
    settings_config: Mapping[str, Any] | None,
) -> None:
    for spec in _THRESHOLD_SPECS:
        sources: list[tuple[str, float]] = []

        manager_value, manager_path = _first_numeric(manager_config, spec.manager_paths)
        if manager_value is not None and manager_path is not None:
            label = "config." + " -> ".join(manager_path)
            sources.append((label, manager_value))

        settings_value, settings_path = _first_numeric(settings_config, spec.settings_paths)
        if settings_value is not None and settings_path is not None:
            label = "settings." + " -> ".join(settings_path)
            sources.append((label, settings_value))

        if not sources:
            continue

        unique_values = {value for _, value in sources}
        if len(unique_values) > 1:
            details = ", ".join(f"{source}={value}" for source, value in sources)
            raise ConfigurationError(
                f"Conflicting {spec.name} configuration detected: {details}"
            )

        for source, value in sources:
            _assert_range(value, spec, source=source)


def _validate_schema_section(schema: Mapping[str, Any], *, source: str) -> None:
    if not isinstance(schema, Mapping):
        raise ConfigurationError(f"{source} must be a mapping of schema settings")

    missing = [
        field for field in _REQUIRED_SCHEMA_FIELDS if not _is_non_empty_string(schema.get(field))
    ]
    if missing:
        raise ConfigurationError(
            f"{source} missing required fields: {', '.join(sorted(missing))}"
        )


def _validate_storage_schema(manager_config: Mapping[str, Any] | None) -> None:
    mapping = _as_mapping(manager_config)
    if mapping is None:
        return

    shared_schema = _extract_nested(mapping, ("storage", "schema"))
    if isinstance(shared_schema, Mapping):
        _validate_schema_section(shared_schema, source="config.storage.schema")

    for tier in ("stm", "mtm", "ltm"):
        tier_schema = _extract_nested(mapping, (tier, "storage", "schema"))
        if isinstance(tier_schema, Mapping):
            _validate_schema_section(tier_schema, source=f"config.{tier}.storage.schema")


def validate_memory_manager_configuration(
    manager_config: Mapping[str, Any] | None,
    *,
    settings_config: Mapping[str, Any] | None = None,
) -> None:
    """Validate merged configuration before constructing the memory manager."""

    _validate_thresholds(manager_config, settings_config)
    _validate_storage_schema(manager_config)
