"""
Base interface for memory systems used in benchmarking.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass
import time
import uuid


@dataclass
class MemoryEntry:
    """Standard memory entry for benchmarking."""
    id: str
    content: str
    metadata: Dict[str, Any]
    timestamp: float
    
    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())
        if not self.timestamp:
            self.timestamp = time.time()


class MemorySystemInterface(ABC):
    """Abstract interface for memory systems used in benchmarking."""
    
    @abstractmethod
    def store(self, entry: MemoryEntry) -> str:
        """Store a memory entry and return its ID."""
        pass
    
    @abstractmethod
    def retrieve(self, entry_id: str) -> Optional[MemoryEntry]:
        """Retrieve a memory entry by ID."""
        pass
    
    @abstractmethod
    def search(self, query: str, limit: int = 10) -> List[MemoryEntry]:
        """Search for memory entries matching the query."""
        pass
    
    @abstractmethod
    def update(self, entry_id: str, entry: MemoryEntry) -> bool:
        """Update an existing memory entry."""
        pass
    
    @abstractmethod
    def delete(self, entry_id: str) -> bool:
        """Delete a memory entry."""
        pass
    
    @abstractmethod
    def list_all(self, limit: Optional[int] = None) -> List[MemoryEntry]:
        """List all memory entries."""
        pass
    
    @abstractmethod
    def count(self) -> int:
        """Return the total number of stored entries."""
        pass
    
    @abstractmethod
    def clear(self) -> None:
        """Clear all memory entries."""
        pass
    
    @abstractmethod
    def get_name(self) -> str:
        """Return the name of the memory system."""
        pass
    
    @abstractmethod
    def get_metadata(self) -> Dict[str, Any]:
        """Return system metadata for benchmarking."""
        pass