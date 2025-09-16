"""Factory helpers for constructing legacy memory systems with monitoring."""

from __future__ import annotations

import logging
from typing import Optional, Type

from neuroca.core.memory.health import register_memory_system
from neuroca.core.memory.interfaces import MemorySystem

logger = logging.getLogger(__name__)

_memory_system_registry: dict[str, Type[MemorySystem]] = {}
_memory_type_aliases = {
    "working_memory": "working",
    "stm": "working",
    "short_term": "working",
    "episodic_memory": "episodic",
    "mtm": "episodic",
    "medium_term": "episodic",
    "semantic_memory": "semantic",
    "ltm": "semantic",
    "long_term": "semantic",
}


def register_memory_implementation(memory_type: str, implementation: Type[MemorySystem]) -> None:
    _memory_system_registry[memory_type.lower()] = implementation


def create_memory_system(
    memory_type: str,
    *,
    enable_health_monitoring: bool = True,
    component_id: Optional[str] = None,
    **config: object,
) -> MemorySystem:
    _register_defaults()
    normalized_type = _memory_type_aliases.get(memory_type.lower(), memory_type.lower())
    if normalized_type not in _memory_system_registry:
        valid = sorted(set(_memory_system_registry) | set(_memory_type_aliases))
        raise ValueError(f"Unknown memory type: {memory_type}. Valid types: {valid}")

    implementation = _memory_system_registry[normalized_type]
    memory_system = implementation(**config)

    if enable_health_monitoring:
        try:
            health = register_memory_system(memory_system, normalized_type, component_id)
            logger.debug(
                "Registered %s memory for health monitoring as %s", normalized_type, health.component_id
            )
        except Exception as exc:  # pragma: no cover - monitoring failures should not crash
            logger.warning("Failed to register %s memory for health monitoring: %s", normalized_type, exc)

    return memory_system


def create_memory_trio(
    *,
    enable_health_monitoring: bool = True,
    prefix: str | None = None,
) -> dict[str, MemorySystem]:
    working_id = f"{prefix}working_memory" if prefix else None
    episodic_id = f"{prefix}episodic_memory" if prefix else None
    semantic_id = f"{prefix}semantic_memory" if prefix else None

    return {
        "working": create_memory_system("working", enable_health_monitoring=enable_health_monitoring, component_id=working_id),
        "episodic": create_memory_system(
            "episodic", enable_health_monitoring=enable_health_monitoring, component_id=episodic_id
        ),
        "semantic": create_memory_system(
            "semantic", enable_health_monitoring=enable_health_monitoring, component_id=semantic_id
        ),
    }


def _register_defaults() -> None:
    if _memory_system_registry:
        return

    from neuroca.core.memory.episodic_memory import EpisodicMemory
    from neuroca.core.memory.working_memory import WorkingMemory
    from neuroca.memory.semantic_memory import SemanticMemory

    register_memory_implementation("working", WorkingMemory)
    register_memory_implementation("episodic", EpisodicMemory)
    register_memory_implementation("semantic", SemanticMemory)

