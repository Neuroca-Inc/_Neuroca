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

# Export the async, interface-driven manager as the primary entry point while
# retaining an alias to the legacy implementation for any remaining
# compatibility shims during the stabilization effort.
MemoryManager = AsyncMemoryManager

__all__ = [
    "MemoryManager",
    "AsyncMemoryManager",
    "LegacyMemoryManager",
    "RankedMemory",
    "MemoryItem",
    "MemoryType",
]
