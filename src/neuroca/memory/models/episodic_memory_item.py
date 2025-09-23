"""Compatibility shim for legacy episodic memory items."""

from __future__ import annotations

from neuroca.memory.models.memory_item import MemoryItem


class EpisodicMemoryItem(MemoryItem):
    """Represent an episodic memory item for compatibility layers.

    The historical synchronous memory facade expects dedicated episodic memory
    item types even though the modern implementation consolidates shared
    functionality inside :class:`MemoryItem`.  The shim inherits from the base
    type to keep import paths stable without duplicating behaviour.
    """

    pass
