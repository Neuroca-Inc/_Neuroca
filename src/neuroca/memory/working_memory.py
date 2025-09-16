"""Public async-friendly façade for the legacy working-memory implementation."""

from __future__ import annotations

from typing import Any, List, Optional

from neuroca.core.memory.working_memory import (
    WorkingMemory as SyncWorkingMemory,
    WorkingMemoryChunk,
)


class WorkingMemory(SyncWorkingMemory):
    """Extend the synchronous working memory with async helper methods."""

    async def search_by_similarity(
        self,
        query: str,
        limit: int = 10,
        threshold: float = 0.0,
    ) -> List[WorkingMemoryChunk]:
        """Perform a simple substring search respecting the provided limit."""

        results = self.retrieve(query, limit=limit)
        if threshold > 0:
            results = [chunk for chunk in results if chunk.activation >= threshold]
        return results

    async def get_recent_items(self, limit: int = 10) -> List[WorkingMemoryChunk]:
        """Return the most recently accessed working-memory chunks."""

        chunks = sorted(
            self.retrieve_all(),
            key=lambda chunk: chunk.last_accessed,
            reverse=True,
        )
        return chunks[:limit]

    async def get_important_items(self, limit: int = 10) -> List[WorkingMemoryChunk]:
        """Return the highest-activation working-memory chunks."""

        chunks = sorted(
            self.retrieve_all(),
            key=lambda chunk: chunk.activation,
            reverse=True,
        )
        return chunks[:limit]

    async def get_item(self, item_id: str) -> Optional[WorkingMemoryChunk]:
        """Retrieve an individual working-memory chunk by identifier."""

        return self.retrieve_by_id(item_id)

    def add(self, content: Any, **metadata: Any) -> str:
        """Compatibility alias for :meth:`store`."""

        return self.store(content, **metadata)

    def delete(self, item_id: str) -> bool:
        """Compatibility alias for :meth:`forget`."""

        return self.forget(item_id)


# Backwards compatible alias used by some API wiring.
WorkingMemoryManager = WorkingMemory

__all__ = ["WorkingMemory", "WorkingMemoryChunk", "WorkingMemoryManager"]
