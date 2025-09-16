"""Legacy synchronous memory modules kept for backwards compatibility."""

from neuroca.core.memory.factory import create_memory_system, create_memory_trio
from neuroca.core.memory.health import (
    EpisodicMemoryHealthCheck,
    MemoryHealthMonitor,
    SemanticMemoryHealthCheck,
    WorkingMemoryHealthCheck,
    get_memory_health_monitor,
    record_memory_operation,
    register_memory_system,
)
from neuroca.core.memory.episodic_memory import EpisodicMemory, EpisodicMemoryChunk
from neuroca.core.memory.working_memory import WorkingMemory, WorkingMemoryChunk

__all__ = [
    "create_memory_system",
    "create_memory_trio",
    "register_memory_system",
    "get_memory_health_monitor",
    "record_memory_operation",
    "WorkingMemory",
    "WorkingMemoryChunk",
    "EpisodicMemory",
    "EpisodicMemoryChunk",
    "WorkingMemoryHealthCheck",
    "EpisodicMemoryHealthCheck",
    "SemanticMemoryHealthCheck",
    "MemoryHealthMonitor",
]
