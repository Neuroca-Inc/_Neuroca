"""Compatibility shim exposing the legacy ``MemoryQuery`` interface."""

from __future__ import annotations

from typing import Any, Dict


class MemoryQuery:
    """Simple container matching the historical ``MemoryQuery`` contract.

    Parameters
    ----------
    query:
        The textual content to retrieve memories for.
    filters:
        Optional filtering directives carried through to the retrieval layer.
    """

    def __init__(self, query: str, filters: Dict[str, Any] | None = None) -> None:
        self.query = query
        self.filters = filters or {}
