"""
Memory Models (Stub)

This module provides stub implementations of memory models to satisfy imports
while the main memory system uses the tier-based architecture.
"""

import logging
from typing import Any, Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class MemoryItem:
    """Base memory item stub."""
    
    def __init__(self, content: Any = None, metadata: Optional[Dict[str, Any]] = None):
        self.content = content
        self.metadata = metadata or {}
        self.created_at = datetime.now()


class WorkingMemoryItem(MemoryItem):
    """Working memory item stub."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class EpisodicMemoryItem(MemoryItem):
    """Episodic memory item stub."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class SemanticMemoryItem(MemoryItem):
    """Semantic memory item stub."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class MemoryQuery:
    """Memory query stub."""
    
    def __init__(self, query: str, filters: Optional[Dict[str, Any]] = None):
        self.query = query
        self.filters = filters or {}


class MemoryRetrievalResult:
    """Memory retrieval result stub."""
    
    def __init__(self, item: MemoryItem, relevance: float = 0.0):
        self.item = item
        self.relevance = relevance
        self.content = item.content if item else None
