"""Neuroca memory manager public interface."""

from neuroca.memory.manager.memory_manager import MemoryManager
from neuroca.memory.manager.models import RankedMemory
from neuroca.memory.models.memory_item import MemoryItem

# Retain a backwards-compatible alias for callers that previously referenced the
# async implementation explicitly. The project now maintains a single manager
# implementation exposed as ``MemoryManager``.
AsyncMemoryManager = MemoryManager

__all__ = [
    "MemoryManager",
    "AsyncMemoryManager",
    "RankedMemory",
    "MemoryItem",
]
