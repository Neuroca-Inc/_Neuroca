"""
Mock NeuroCognitive Architecture memory system for benchmarking.
This simulates the NCA memory system without requiring full dependencies.
"""
import time
from typing import Any, Dict, List, Optional
from ..base import MemorySystemInterface, MemoryEntry


class NeurocognitiveArchitectureMemory(MemorySystemInterface):
    """
    Mock implementation of the NeuroCognitive Architecture memory system.
    Simulates the multi-tier memory approach with STM, MTM, and LTM.
    """
    
    def __init__(self):
        # Simulate three memory tiers
        self.stm_storage = {}  # Short-term: fast access, limited capacity
        self.mtm_storage = {}  # Medium-term: structured storage
        self.ltm_storage = {}  # Long-term: persistent, semantic storage
        
        # Configuration
        self.stm_max_items = 50
        self.mtm_max_items = 500
        self.stm_retention_time = 300  # 5 minutes
        self.mtm_retention_time = 86400  # 24 hours
        
        # Metadata
        self.created_at = time.time()
        self.access_count = 0
        self.consolidation_count = 0
    
    def _should_consolidate_to_mtm(self, entry: MemoryEntry) -> bool:
        """Determine if entry should move from STM to MTM."""
        age = time.time() - entry.timestamp
        importance = entry.metadata.get('importance', 0.5)
        access_count = entry.metadata.get('access_count', 0)
        
        # Consolidate based on age, importance, or access frequency
        return (age > self.stm_retention_time or 
                importance > 0.8 or 
                access_count > 3)
    
    def _should_consolidate_to_ltm(self, entry: MemoryEntry) -> bool:
        """Determine if entry should move from MTM to LTM."""
        age = time.time() - entry.timestamp
        importance = entry.metadata.get('importance', 0.5)
        access_count = entry.metadata.get('access_count', 0)
        
        # Consolidate to LTM based on long-term criteria
        return (age > self.mtm_retention_time or
                importance > 0.9 or
                access_count > 10)
    
    def _consolidate_memories(self):
        """Simulate memory consolidation process."""
        current_time = time.time()
        
        # STM to MTM consolidation
        stm_to_remove = []
        for entry_id, entry in self.stm_storage.items():
            if self._should_consolidate_to_mtm(entry):
                self.mtm_storage[entry_id] = entry
                stm_to_remove.append(entry_id)
                self.consolidation_count += 1
        
        for entry_id in stm_to_remove:
            del self.stm_storage[entry_id]
        
        # MTM to LTM consolidation
        mtm_to_remove = []
        for entry_id, entry in self.mtm_storage.items():
            if self._should_consolidate_to_ltm(entry):
                self.ltm_storage[entry_id] = entry
                mtm_to_remove.append(entry_id)
                self.consolidation_count += 1
        
        for entry_id in mtm_to_remove:
            del self.mtm_storage[entry_id]
        
        # Cleanup old STM entries
        for entry_id in list(self.stm_storage.keys()):
            entry = self.stm_storage[entry_id]
            if current_time - entry.timestamp > self.stm_retention_time * 2:
                del self.stm_storage[entry_id]
        
        # STM capacity management
        if len(self.stm_storage) > self.stm_max_items:
            # Remove oldest entries
            sorted_stm = sorted(
                self.stm_storage.items(),
                key=lambda x: x[1].timestamp
            )
            for entry_id, _ in sorted_stm[:-self.stm_max_items]:
                del self.stm_storage[entry_id]
        
        # MTM capacity management
        if len(self.mtm_storage) > self.mtm_max_items:
            # Remove oldest, least important entries
            sorted_mtm = sorted(
                self.mtm_storage.items(),
                key=lambda x: (x[1].metadata.get('importance', 0.5), x[1].timestamp)
            )
            for entry_id, _ in sorted_mtm[:-self.mtm_max_items]:
                del self.mtm_storage[entry_id]
    
    def store(self, entry: MemoryEntry) -> str:
        """Store a memory entry (starts in STM)."""
        # Always start in STM
        self.stm_storage[entry.id] = entry
        
        # Trigger consolidation
        self._consolidate_memories()
        
        return entry.id
    
    def retrieve(self, entry_id: str) -> Optional[MemoryEntry]:
        """Retrieve a memory entry from any tier."""
        self.access_count += 1
        
        # Check STM first (fastest)
        if entry_id in self.stm_storage:
            entry = self.stm_storage[entry_id]
            # Update access count
            entry.metadata['access_count'] = entry.metadata.get('access_count', 0) + 1
            return entry
        
        # Check MTM
        if entry_id in self.mtm_storage:
            entry = self.mtm_storage[entry_id]
            entry.metadata['access_count'] = entry.metadata.get('access_count', 0) + 1
            # Promote to STM for future fast access
            self.stm_storage[entry_id] = entry
            return entry
        
        # Check LTM
        if entry_id in self.ltm_storage:
            entry = self.ltm_storage[entry_id]
            entry.metadata['access_count'] = entry.metadata.get('access_count', 0) + 1
            # Promote to STM for future fast access
            self.stm_storage[entry_id] = entry
            return entry
        
        return None
    
    def search(self, query: str, limit: int = 10) -> List[MemoryEntry]:
        """Search across all memory tiers."""
        query_lower = query.lower()
        results = []
        
        # Search STM first (most recent/relevant)
        for entry in self.stm_storage.values():
            if (query_lower in entry.content.lower() or
                any(query_lower in str(v).lower() for v in entry.metadata.values())):
                results.append(entry)
        
        # Search MTM
        for entry in self.mtm_storage.values():
            if len(results) >= limit:
                break
            if (query_lower in entry.content.lower() or
                any(query_lower in str(v).lower() for v in entry.metadata.values())):
                results.append(entry)
        
        # Search LTM
        for entry in self.ltm_storage.values():
            if len(results) >= limit:
                break
            if (query_lower in entry.content.lower() or
                any(query_lower in str(v).lower() for v in entry.metadata.values())):
                results.append(entry)
        
        # Sort by relevance (importance + recency)
        results.sort(
            key=lambda x: (
                x.metadata.get('importance', 0.5),
                x.timestamp,
                x.metadata.get('access_count', 0)
            ),
            reverse=True
        )
        
        return results[:limit]
    
    def update(self, entry_id: str, entry: MemoryEntry) -> bool:
        """Update an existing memory entry."""
        entry.id = entry_id
        
        # Find and update in appropriate tier
        if entry_id in self.stm_storage:
            self.stm_storage[entry_id] = entry
            return True
        elif entry_id in self.mtm_storage:
            self.mtm_storage[entry_id] = entry
            return True
        elif entry_id in self.ltm_storage:
            self.ltm_storage[entry_id] = entry
            return True
        
        return False
    
    def delete(self, entry_id: str) -> bool:
        """Delete a memory entry from all tiers."""
        deleted = False
        
        if entry_id in self.stm_storage:
            del self.stm_storage[entry_id]
            deleted = True
        
        if entry_id in self.mtm_storage:
            del self.mtm_storage[entry_id]
            deleted = True
        
        if entry_id in self.ltm_storage:
            del self.ltm_storage[entry_id]
            deleted = True
        
        return deleted
    
    def list_all(self, limit: Optional[int] = None) -> List[MemoryEntry]:
        """List all memory entries from all tiers."""
        all_entries = []
        
        # Collect from all tiers
        all_entries.extend(self.stm_storage.values())
        all_entries.extend(self.mtm_storage.values())
        all_entries.extend(self.ltm_storage.values())
        
        # Remove duplicates (in case of promotion)
        seen_ids = set()
        unique_entries = []
        for entry in all_entries:
            if entry.id not in seen_ids:
                unique_entries.append(entry)
                seen_ids.add(entry.id)
        
        # Sort by timestamp
        unique_entries.sort(key=lambda x: x.timestamp, reverse=True)
        
        if limit is not None:
            unique_entries = unique_entries[:limit]
        
        return unique_entries
    
    def count(self) -> int:
        """Return the total number of unique stored entries."""
        all_ids = set()
        all_ids.update(self.stm_storage.keys())
        all_ids.update(self.mtm_storage.keys())
        all_ids.update(self.ltm_storage.keys())
        return len(all_ids)
    
    def clear(self) -> None:
        """Clear all memory entries."""
        self.stm_storage.clear()
        self.mtm_storage.clear()
        self.ltm_storage.clear()
    
    def get_name(self) -> str:
        """Return the name of the memory system."""
        return "NeuroCognitive Architecture Memory"
    
    def get_metadata(self) -> Dict[str, Any]:
        """Return system metadata."""
        return {
            "name": self.get_name(),
            "type": "hybrid",
            "storage_type": "multi_tier",
            "persistent": True,
            "supports_transactions": True,
            "supports_indexing": True,
            "search_method": "multi_tier_hierarchical",
            "tiers": {
                "stm": {
                    "count": len(self.stm_storage),
                    "max_items": self.stm_max_items,
                    "retention_time": self.stm_retention_time
                },
                "mtm": {
                    "count": len(self.mtm_storage),
                    "max_items": self.mtm_max_items,
                    "retention_time": self.mtm_retention_time
                },
                "ltm": {
                    "count": len(self.ltm_storage),
                    "unlimited": True
                }
            },
            "access_count": self.access_count,
            "consolidation_count": self.consolidation_count,
            "created_at": self.created_at,
            "entry_count": self.count()
        }