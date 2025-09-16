"""Public re-export of the legacy synchronous working-memory implementation."""

from neuroca.core.memory.working_memory import WorkingMemory, WorkingMemoryChunk

# Backwards compatible alias used by some API wiring.
WorkingMemoryManager = WorkingMemory

__all__ = ["WorkingMemory", "WorkingMemoryChunk", "WorkingMemoryManager"]
