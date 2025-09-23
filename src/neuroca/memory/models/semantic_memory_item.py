"""Compatibility shim for legacy semantic memory items."""

from __future__ import annotations

from neuroca.memory.models.memory_item import MemoryItem


class SemanticMemoryItem(MemoryItem):
    """Represent a semantic memory item for compatibility layers.

    Legacy synchronous entry points historically imported a dedicated semantic
    memory item class even though the modern system relies on the common
    :class:`MemoryItem` model.  The shim maintains backwards compatibility while
    delegating all behaviour to the shared implementation.
    """

    pass
