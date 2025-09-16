"""Public re-export of the legacy synchronous episodic-memory implementation."""

from neuroca.core.memory.episodic_memory import EpisodicMemory, EpisodicMemoryChunk

# Compatibility alias for downstream imports expecting a manager naming convention.
EpisodicMemoryManager = EpisodicMemory

__all__ = ["EpisodicMemory", "EpisodicMemoryChunk", "EpisodicMemoryManager"]
