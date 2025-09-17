"""
Simple in-memory dictionary-based memory system for baseline comparison.
"""
from typing import Any, Dict, List, Optional
import time
from ..base import MemorySystemInterface, MemoryEntry


class SimpleDictMemory(MemorySystemInterface):
    """
    Simple dictionary-based memory system.
    Uses Python dictionaries for storage with basic text search.
    """
    
    def __init__(self):
        self.storage: Dict[str, MemoryEntry] = {}
        self.created_at = time.time()
    
    def store(self, entry: MemoryEntry) -> str:
        """Store a memory entry."""
        self.storage[entry.id] = entry
        return entry.id
    
    def retrieve(self, entry_id: str) -> Optional[MemoryEntry]:
        """Retrieve a memory entry by ID."""
        return self.storage.get(entry_id)
    
    def search(self, query: str, limit: int = 10) -> List[MemoryEntry]:
        """Search for entries containing the query text."""
        query_lower = query.lower()
        results = []
        
        for entry in self.storage.values():
            # Simple text search in content and metadata
            if (query_lower in entry.content.lower() or
                any(query_lower in str(v).lower() for v in entry.metadata.values())):
                results.append(entry)
                
            if len(results) >= limit:
                break
        
        # Sort by timestamp (most recent first)
        results.sort(key=lambda x: x.timestamp, reverse=True)
        return results[:limit]
    
    def update(self, entry_id: str, entry: MemoryEntry) -> bool:
        """Update an existing memory entry."""
        if entry_id in self.storage:
            entry.id = entry_id  # Ensure ID consistency
            self.storage[entry_id] = entry
            return True
        return False
    
    def delete(self, entry_id: str) -> bool:
        """Delete a memory entry."""
        if entry_id in self.storage:
            del self.storage[entry_id]
            return True
        return False
    
    def list_all(self, limit: Optional[int] = None) -> List[MemoryEntry]:
        """List all memory entries."""
        entries = list(self.storage.values())
        entries.sort(key=lambda x: x.timestamp, reverse=True)
        
        if limit is not None:
            entries = entries[:limit]
        
        return entries
    
    def count(self) -> int:
        """Return the total number of stored entries."""
        return len(self.storage)
    
    def clear(self) -> None:
        """Clear all memory entries."""
        self.storage.clear()
    
    def get_name(self) -> str:
        """Return the name of the memory system."""
        return "Simple Dictionary Memory"
    
    def get_metadata(self) -> Dict[str, Any]:
        """Return system metadata."""
        return {
            "name": self.get_name(),
            "type": "in_memory",
            "storage_type": "python_dict",
            "persistent": False,
            "supports_transactions": False,
            "supports_indexing": False,
            "search_method": "full_text_scan",
            "created_at": self.created_at,
            "entry_count": self.count()
        }