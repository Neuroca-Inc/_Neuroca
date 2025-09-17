"""Neuroca memory manager public interface."""

from enum import Enum

from neuroca.memory.manager.memory_manager import MemoryManager as AsyncMemoryManager
from neuroca.memory.manager.core import MemoryManager as LegacyMemoryManager
from neuroca.memory.manager.models import RankedMemory
from neuroca.memory.models import MemoryItem


class MemoryType(str, Enum):
    """Legacy memory type enumeration retained for compatibility."""

    WORKING = "working"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"

# Retain a backwards-compatible alias for callers that previously referenced the
# async implementation explicitly. The project now maintains a single manager
# implementation exposed as ``MemoryManager``.
AsyncMemoryManager = MemoryManager

__all__ = [
    "MemoryManager",
    "AsyncMemoryManager",
    "RankedMemory",
    "MemoryItem",
    "MemoryType",
]
