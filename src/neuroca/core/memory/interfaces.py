"""Core memory system interfaces used by legacy compatibility layers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Generic, Iterable, Optional, TypeVar

T = TypeVar("T")


class MemoryChunk(Generic[T], ABC):
    """Abstract representation of a chunk stored inside a memory system."""

    @property
    @abstractmethod
    def id(self) -> str:
        """Return the stable identifier for this chunk."""

    @property
    @abstractmethod
    def content(self) -> T:
        """Return the user supplied content for this chunk."""

    @property
    @abstractmethod
    def activation(self) -> float:
        """Return the current activation strength of the chunk."""

    @property
    @abstractmethod
    def created_at(self) -> datetime:
        """Return when the chunk was created."""

    @property
    @abstractmethod
    def last_accessed(self) -> datetime:
        """Return when the chunk was last accessed."""

    @property
    @abstractmethod
    def metadata(self) -> dict[str, Any]:
        """Return chunk metadata such as tags or contextual information."""

    @abstractmethod
    def update_activation(self, value: Optional[float] = None) -> None:
        """Refresh the activation level, optionally forcing a specific value."""


class MemorySystem(ABC):
    """Common protocol implemented by the legacy synchronous memory classes."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the display name for the memory system."""

    @property
    @abstractmethod
    def capacity(self) -> Optional[int]:
        """Return the maximum number of chunks if the system is bounded."""

    @abstractmethod
    def store(self, content: Any, **metadata: Any) -> str:
        """Persist content inside the memory system and return the chunk id."""

    @abstractmethod
    def retrieve(self, query: Any, limit: int = 10, **parameters: Any) -> list[MemoryChunk]:
        """Retrieve chunks matching the supplied query semantics."""

    @abstractmethod
    def retrieve_by_id(self, chunk_id: str) -> Optional[MemoryChunk]:
        """Fetch a chunk by its identifier."""

    @abstractmethod
    def forget(self, chunk_id: str) -> bool:
        """Remove the chunk with the supplied identifier if present."""

    @abstractmethod
    def clear(self) -> None:
        """Remove all chunks from the memory system."""

    @abstractmethod
    def dump(self) -> list[dict[str, Any]]:
        """Return a serialisable representation of every stored chunk."""

    def retrieve_all(self) -> list[MemoryChunk]:
        """Return every chunk currently stored inside the system."""
        return list(self.iter_chunks())

    def iter_chunks(self) -> Iterable[MemoryChunk]:
        """Iterate through all chunks held by the memory system."""
        return iter(self.retrieve_all())

    def get_all_items(self) -> list[MemoryChunk]:
        """Backwards compatibility alias for :meth:`retrieve_all`."""
        return self.retrieve_all()

    def get_statistics(self) -> dict[str, Any]:
        """Return basic statistics for health reporting."""
        return {
            "name": self.name,
            "capacity": self.capacity,
            "total_items": len(self.retrieve_all()),
        }
