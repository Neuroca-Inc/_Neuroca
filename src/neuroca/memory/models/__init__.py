"""
Memory System Data Models

This package contains the Pydantic models used throughout the memory system.
These models define the structure and validation rules for data passed between
components of the memory system.

Core Models:
- MemoryItem: The basic unit of memory storage
- MemoryMetadata: Metadata associated with memory items
- MemoryContent: Content of a memory item
- MemorySearchResult: Result from a memory search operation
- WorkingMemoryItem: Memory item in the working memory buffer
"""

from neuroca.memory.models.memory_item import (
    MemoryItem,
    MemoryMetadata,
    MemoryContent,
    MemoryStatus,
)
from neuroca.memory.models.search import (
    MemorySearchResult,
    MemorySearchOptions,
)
from neuroca.memory.models.working_memory import (
    WorkingMemoryItem,
    WorkingMemoryBuffer,
)

# Add stub classes for compatibility
class EpisodicMemoryItem(MemoryItem):
    """Stub episodic memory item for compatibility."""
    pass

class SemanticMemoryItem(MemoryItem):
    """Stub semantic memory item for compatibility."""
    pass

class MemoryQuery:
    """Stub memory query for compatibility."""
    def __init__(self, query: str, filters=None):
        self.query = query
        self.filters = filters or {}

class MemoryRetrievalResult:
    """Stub memory retrieval result for compatibility."""
    def __init__(self, item=None, relevance: float = 0.0):
        self.item = item
        self.relevance = relevance
        self.content = item.content if item else None

__all__ = [
    # Memory Item Models
    "MemoryItem",
    "MemoryMetadata",
    "MemoryContent",
    "MemoryStatus",
    
    # Search Models
    "MemorySearchResult",
    "MemorySearchOptions",
    
    # Working Memory Models
    "WorkingMemoryItem",
    "WorkingMemoryBuffer",
    
    # Compatibility stubs
    "EpisodicMemoryItem",
    "SemanticMemoryItem", 
    "MemoryQuery",
    "MemoryRetrievalResult",
]
