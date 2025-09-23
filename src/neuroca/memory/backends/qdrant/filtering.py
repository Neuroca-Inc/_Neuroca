"""Filtering and metadata helpers for the Qdrant backend."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

__all__ = [
    "attach_relevance",
    "extract_nested_value",
    "matches_filters",
]


def attach_relevance(metadata: Dict[str, Any], score: Optional[float]) -> None:
    """Attach a similarity score to ``metadata`` when provided.

    Args:
        metadata: Dictionary that will be mutated to include a ``relevance``
            field describing the similarity score associated with a search hit.
        score: Optional score returned by Qdrant. ``None`` values are ignored.

    This function mutates ``metadata`` in-place to avoid unnecessary
    allocations when decorating search payloads.
    """

    if score is None:
        return
    metadata.setdefault("relevance", float(score))


def extract_nested_value(payload: Dict[str, Any], dotted_key: str) -> Any:
    """Return the nested value referenced by ``dotted_key`` from ``payload``.

    Args:
        payload: Arbitrary metadata payload returned by Qdrant.
        dotted_key: Dot-delimited key identifying the desired nested value.

    Returns:
        The value found at the requested path, or ``None`` when any component
        of the path is missing.
    """

    current: Any = payload
    for part in dotted_key.split("."):
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


def _normalize_sequence(value: Iterable[Any]) -> List[Any]:
    """Coerce ``value`` into a list without expanding strings character-by-character."""

    if isinstance(value, (str, bytes)):
        return [value]
    return list(value)


def matches_filters(payload: Dict[str, Any], filters: Dict[str, Any]) -> bool:
    """Return ``True`` when ``payload`` satisfies ``filters``.

    Args:
        payload: Payload dictionary returned by Qdrant.
        filters: Neuroca-style filter definition supporting ``$exists``,
            ``$in``/``$any``, and ``$all`` semantics.

    Returns:
        ``True`` if the payload matches all filter criteria, otherwise ``False``.
    """

    for key, expected in filters.items():
        actual = extract_nested_value(payload, key)
        if isinstance(expected, dict):
            for op, value in expected.items():
                if op == "$exists":
                    exists = actual is not None
                    if bool(value) != exists:
                        return False
                elif op in {"$in", "$any"}:
                    candidates = _normalize_sequence(value)
                    if isinstance(actual, list):
                        if not any(item in actual for item in candidates):
                            return False
                    elif actual not in candidates:
                        return False
                elif op == "$all":
                    candidates = _normalize_sequence(value)
                    if not isinstance(actual, list) or not all(item in actual for item in candidates):
                        return False
                else:
                    if not isinstance(actual, dict) or not matches_filters(actual, {op: value}):
                        return False
        else:
            if isinstance(actual, list):
                if expected not in actual:
                    return False
            elif actual != expected:
                return False
    return True
