"""
LangChain-inspired memory system for comparison.
This simulates LangChain's conversation buffer memory approach.
"""
from typing import Any, Dict, List, Optional
import time
from collections import deque
from ..base import MemorySystemInterface, MemoryEntry


class LangChainInspiredMemory(MemorySystemInterface):
    """
    Memory system inspired by LangChain's ConversationBufferMemory.
    Uses a sliding window approach with token-based limits.
    """
    
    def __init__(self, max_token_limit: int = 2000, max_entries: int = 100):
        self.max_token_limit = max_token_limit
        self.max_entries = max_entries
        self.buffer = deque(maxlen=max_entries)
        self.entry_lookup: Dict[str, MemoryEntry] = {}
        self.created_at = time.time()
    
    def _estimate_tokens(self, text: str) -> int:
        """Simple token estimation (roughly 4 chars per token)."""
        return len(text) // 4
    
    def _maintain_buffer_size(self):
        """Maintain buffer within token and entry limits."""
        total_tokens = sum(
            self._estimate_tokens(entry.content) + 
            self._estimate_tokens(str(entry.metadata))
            for entry in self.buffer
        )
        
        # Remove oldest entries if we exceed token limit
        while total_tokens > self.max_token_limit and self.buffer:
            oldest = self.buffer.popleft()
            if oldest.id in self.entry_lookup:
                del self.entry_lookup[oldest.id]
            
            total_tokens = sum(
                self._estimate_tokens(entry.content) + 
                self._estimate_tokens(str(entry.metadata))
                for entry in self.buffer
            )
    
    def store(self, entry: MemoryEntry) -> str:
        """Store a memory entry in the buffer."""
        # Remove existing entry if updating
        if entry.id in self.entry_lookup:
            old_entry = self.entry_lookup[entry.id]
            try:
                self.buffer.remove(old_entry)
            except ValueError:
                pass
        
        # Add to buffer and lookup
        self.buffer.append(entry)
        self.entry_lookup[entry.id] = entry
        
        # Maintain size limits
        self._maintain_buffer_size()
        
        return entry.id
    
    def retrieve(self, entry_id: str) -> Optional[MemoryEntry]:
        """Retrieve a memory entry by ID."""
        return self.entry_lookup.get(entry_id)
    
    def search(self, query: str, limit: int = 10) -> List[MemoryEntry]:
        """Search for entries containing the query text."""
        query_lower = query.lower()
        results = []
        
        # Search in reverse order (most recent first)
        for entry in reversed(self.buffer):
            if (query_lower in entry.content.lower() or
                any(query_lower in str(v).lower() for v in entry.metadata.values())):
                results.append(entry)
                
            if len(results) >= limit:
                break
        
        return results
    
    def update(self, entry_id: str, entry: MemoryEntry) -> bool:
        """Update an existing memory entry."""
        if entry_id in self.entry_lookup:
            entry.id = entry_id
            return self.store(entry) == entry_id
        return False
    
    def delete(self, entry_id: str) -> bool:
        """Delete a memory entry."""
        if entry_id in self.entry_lookup:
            entry = self.entry_lookup[entry_id]
            try:
                self.buffer.remove(entry)
                del self.entry_lookup[entry_id]
                return True
            except ValueError:
                pass
        return False
    
    def list_all(self, limit: Optional[int] = None) -> List[MemoryEntry]:
        """List all memory entries."""
        entries = list(reversed(self.buffer))  # Most recent first
        
        if limit is not None:
            entries = entries[:limit]
        
        return entries
    
    def count(self) -> int:
        """Return the total number of stored entries."""
        return len(self.buffer)
    
    def clear(self) -> None:
        """Clear all memory entries."""
        self.buffer.clear()
        self.entry_lookup.clear()
    
    def get_name(self) -> str:
        """Return the name of the memory system."""
        return "LangChain-Inspired Buffer Memory"
    
    def get_metadata(self) -> Dict[str, Any]:
        """Return system metadata."""
        current_tokens = sum(
            self._estimate_tokens(entry.content) + 
            self._estimate_tokens(str(entry.metadata))
            for entry in self.buffer
        )
        
        return {
            "name": self.get_name(),
            "type": "in_memory",
            "storage_type": "circular_buffer",
            "persistent": False,
            "supports_transactions": False,
            "supports_indexing": False,
            "search_method": "sliding_window_scan",
            "max_token_limit": self.max_token_limit,
            "max_entries": self.max_entries,
            "current_tokens": current_tokens,
            "created_at": self.created_at,
            "entry_count": self.count()
        }
    
    def get_context_window(self) -> str:
        """Get the current context window as a single string."""
        return "\n".join(
            f"{entry.metadata.get('role', 'user')}: {entry.content}"
            for entry in self.buffer
        )