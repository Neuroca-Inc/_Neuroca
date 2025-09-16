"""Public async-friendly façade for the legacy episodic-memory implementation."""

from __future__ import annotations

from typing import Any, List, Optional

from neuroca.core.memory.episodic_memory import (
    EpisodicMemory as SyncEpisodicMemory,
    EpisodicMemoryChunk,
)


class EpisodicMemory(SyncEpisodicMemory):
    """Extend the synchronous episodic memory with async helper methods."""

    async def search_episodes(
        self,
        query: str,
        limit: int = 10,
        threshold: float = 0.0,
    ) -> List[EpisodicMemoryChunk]:
        """Async helper delegating to :meth:`retrieve`."""

        results = self.retrieve(query, limit=limit, min_emotional_salience=threshold)
        return results

    async def get_recent_episodes(self, limit: int = 10) -> List[EpisodicMemoryChunk]:
        """Return the most recently accessed episodes."""

        episodes = sorted(
            self.retrieve_all(),
            key=lambda chunk: (
                chunk.metadata.get("timestamp")
                if hasattr(chunk, "metadata") and chunk.metadata.get("timestamp") is not None
                else chunk.last_accessed.timestamp()
            ),
            reverse=True,
        )
        return episodes[:limit]

    async def get_important_episodes(self, limit: int = 10) -> List[EpisodicMemoryChunk]:
        """Return the most emotionally salient episodes."""

        episodes = sorted(
            self.retrieve_all(),
            key=lambda chunk: chunk.metadata.get("emotional_salience", chunk.emotional_salience),
            reverse=True,
        )
        return episodes[:limit]

    async def get_episode(self, episode_id: str) -> Optional[EpisodicMemoryChunk]:
        """Retrieve a specific episode by identifier."""

        return self.retrieve_by_id(episode_id)

    def add(self, content: Any, **metadata: Any) -> str:
        """Compatibility alias for :meth:`store`."""

        return self.store(content, **metadata)


# Compatibility alias for downstream imports expecting a manager naming convention.
EpisodicMemoryManager = EpisodicMemory

__all__ = ["EpisodicMemory", "EpisodicMemoryChunk", "EpisodicMemoryManager"]
