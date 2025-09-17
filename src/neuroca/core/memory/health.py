"""Memory specific health-monitoring utilities for the legacy API surface."""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

from neuroca.core.enums import MemoryTier
from neuroca.core.health import (
    ComponentHealth,
    HealthCheckResult,
    HealthCheckStatus,
    MemoryHealthCheck,
    record_cognitive_operation,
    register_component_for_health_tracking,
    register_health_check,
)

logger = logging.getLogger(__name__)


def _finalize_health_result(
    check: MemoryHealthCheck,
    start_time: float,
    status: HealthCheckStatus,
    message: str,
    details: dict[str, Any],
) -> HealthCheckResult:
    """Create a ``HealthCheckResult`` and merge tier metrics when available."""

    metrics: dict[str, Any] = {}
    if hasattr(check.memory_system, "get_metrics"):
        try:
            candidate = check.memory_system.get_metrics()
            if isinstance(candidate, dict):
                metrics = candidate
        except Exception:  # pragma: no cover - defensive metrics gathering
            logger.debug("Unable to gather metrics from memory system", exc_info=True)

    combined_details = details | metrics
    result = check.create_result(status, message, **combined_details)
    result.execution_time = (time.time() - start_time) * 1000
    return result


class WorkingMemoryHealthCheck(MemoryHealthCheck):
    """Evaluate capacity pressure and activation levels for working memory."""

    def __init__(
        self,
        component_id: str,
        memory_system,
        *,
        capacity_threshold: float = 0.8,
        activation_threshold: float = 0.3,
    ) -> None:
        super().__init__(
            check_id=f"{component_id}.health",
            component_id=component_id,
            memory_system=memory_system,
            capacity_threshold=capacity_threshold,
        )
        self._activation_threshold = activation_threshold

    def execute(self) -> HealthCheckResult:
        start = time.time()
        try:
            chunks = self.memory_system.get_all_items()
            total_items = len(chunks)
            capacity = getattr(self.memory_system, "capacity", float("inf"))
            capacity_ratio = total_items / capacity if capacity not in (0, float("inf")) else 0.0

            activation_levels = [getattr(chunk, "activation", 0.0) for chunk in chunks]
            avg_activation = sum(activation_levels) / total_items if activation_levels else 0.0
            low_activation_ratio = (
                sum(level < self._activation_threshold for level in activation_levels) / total_items
                if activation_levels
                else 0.0
            )

            test_content = f"health-check-{time.time()}"
            chunk_id = self.memory_system.store(test_content, activation=0.9)
            retrieved = self.memory_system.retrieve_by_id(chunk_id)
            operations_successful = retrieved is not None and getattr(retrieved, "content", None) == test_content
            if retrieved is not None:
                self.memory_system.forget(chunk_id)

            status = HealthCheckStatus.PASSED
            message = "Working memory is operating normally"
            if not operations_successful:
                status = HealthCheckStatus.FAILED
                message = "Working memory operations failed"
            elif low_activation_ratio > 0.5:
                status = HealthCheckStatus.WARNING
                message = (
                    "Working memory has many low activation items "
                    f"({low_activation_ratio:.1%} below threshold)"
                )
            elif capacity_ratio >= self.capacity_threshold:
                status = HealthCheckStatus.WARNING
                message = f"Working memory is nearing capacity ({capacity_ratio:.1%})"

            details = {
                "total_items": total_items,
                "capacity": capacity,
                "capacity_ratio": capacity_ratio,
                "avg_activation": avg_activation,
                "low_activation_ratio": low_activation_ratio,
                "operations_successful": operations_successful,
            }
            return _finalize_health_result(self, start, status, message, details)
        except Exception as exc:  # pragma: no cover - defensive logging path
            logger.exception("Error during working memory health check")
            result = self.create_result(
                HealthCheckStatus.ERROR,
                f"Health check failed with error: {exc}",
                error=str(exc),
                error_type=type(exc).__name__,
            )
            result.execution_time = (time.time() - start) * 1000
            return result


class EpisodicMemoryHealthCheck(MemoryHealthCheck):
    """Validate episodic memory metadata coverage and retrieval semantics."""

    def __init__(self, component_id: str, memory_system) -> None:
        super().__init__(
            check_id=f"{component_id}.health",
            component_id=component_id,
            memory_system=memory_system,
        )

    def execute(self) -> HealthCheckResult:
        start = time.time()
        try:
            chunks = self.memory_system.get_all_items()
            total_items = len(chunks)

            timestamps = [
                chunk.metadata.get("timestamp")
                for chunk in chunks
                if hasattr(chunk, "metadata") and chunk.metadata.get("timestamp") is not None
            ]
            timestamp_ratio = len(timestamps) / total_items if total_items else 0.0
            emotional_salience = [
                chunk.metadata.get("emotional_salience", 0.0) for chunk in chunks if hasattr(chunk, "metadata")
            ]
            avg_emotion = sum(emotional_salience) / total_items if total_items else 0.0
            high_emotion_count = sum(value >= 0.7 for value in emotional_salience)

            test_content = f"health-check-{time.time()}"
            test_metadata = {"timestamp": time.time(), "emotional_salience": 0.5, "health_check": True}
            chunk_id = self.memory_system.store(test_content, metadata=test_metadata)
            retrieved = self.memory_system.retrieve_by_id(chunk_id)
            operations_successful = retrieved is not None and getattr(retrieved, "content", None) == test_content
            metadata_preserved = bool(retrieved and retrieved.metadata.get("timestamp") and retrieved.metadata.get("emotional_salience"))
            if retrieved is not None:
                self.memory_system.forget(chunk_id)

            status = HealthCheckStatus.PASSED
            message = "Episodic memory is operating normally"
            if not operations_successful:
                status = HealthCheckStatus.FAILED
                message = "Episodic memory operations failed"
            elif not metadata_preserved:
                status = HealthCheckStatus.WARNING
                message = "Episodic memory not preserving metadata correctly"
            elif total_items > 0 and timestamp_ratio < 0.8:
                status = HealthCheckStatus.WARNING
                message = f"Many episodic memories lack temporal context ({timestamp_ratio:.1%} have timestamps)"

            details = {
                "total_items": total_items,
                "timestamp_ratio": timestamp_ratio,
                "avg_emotional_salience": avg_emotion,
                "high_emotion_count": high_emotion_count,
                "operations_successful": operations_successful,
                "metadata_preserved": metadata_preserved,
            }
            return _finalize_health_result(self, start, status, message, details)
        except Exception as exc:  # pragma: no cover
            logger.exception("Error during episodic memory health check")
            result = self.create_result(
                HealthCheckStatus.ERROR,
                f"Health check failed with error: {exc}",
                error=str(exc),
                error_type=type(exc).__name__,
            )
            result.execution_time = (time.time() - start) * 1000
            return result


class SemanticMemoryHealthCheck(MemoryHealthCheck):
    """Ensure semantic memory maintains a connected knowledge graph."""

    def __init__(self, component_id: str, memory_system) -> None:
        super().__init__(
            check_id=f"{component_id}.health",
            component_id=component_id,
            memory_system=memory_system,
        )

    def execute(self) -> HealthCheckResult:
        start = time.time()
        try:
            concepts = self.memory_system.retrieve_all_concepts()
            relationships = self.memory_system.retrieve_all_relationships()
            total_concepts = len(concepts)
            total_relationships = len(relationships)

            concept_ids = {concept.id for concept in concepts}
            orphaned_relationships = sum(
                rel.source_id not in concept_ids or rel.target_id not in concept_ids
                for rel in relationships
            )

            connected_concepts = {
                rel.source_id
                for rel in relationships
                if rel.source_id in concept_ids and rel.target_id in concept_ids
            }
            connected_concepts.update(
                rel.target_id for rel in relationships if rel.source_id in concept_ids and rel.target_id in concept_ids
            )
            connectivity_ratio = len(connected_concepts) / total_concepts if total_concepts else 0.0

            test_concept_id = f"health-check-{int(time.time())}"
            test_concept = self.memory_system._create_concept(
                id=test_concept_id,
                name="Health Check Concept",
                description="Temporary concept created by health monitoring",
                properties={"temporary": True},
            )
            self.memory_system.store(test_concept)
            retrieved_concept = self.memory_system.get_concept(test_concept_id)
            concept_ops_successful = retrieved_concept is not None

            relationship_ops_successful = False
            if concept_ops_successful and concepts:
                candidate = concepts[0]
                test_relationship = self.memory_system._create_relationship(
                    source_id=test_concept_id,
                    target_id=candidate.id,
                    relationship_type="HEALTH_CHECK",
                )
                self.memory_system.store(test_relationship)
                relationship_ops_successful = bool(
                    self.memory_system.retrieve_relationships_for_concept(test_concept_id)
                )

            if concept_ops_successful:
                self.memory_system.forget_concept(test_concept_id)

            status = HealthCheckStatus.PASSED
            message = "Semantic memory is operating normally"
            if not concept_ops_successful:
                status = HealthCheckStatus.FAILED
                message = "Semantic memory concept operations failed"
            elif orphaned_relationships > 0:
                status = HealthCheckStatus.WARNING
                message = f"Semantic memory contains {orphaned_relationships} orphaned relationships"
            elif connectivity_ratio < 0.5 and total_concepts > 5:
                status = HealthCheckStatus.WARNING
                message = f"Low concept connectivity ({connectivity_ratio:.1%} concepts connected)"

            details = {
                "total_concepts": total_concepts,
                "total_relationships": total_relationships,
                "orphaned_relationships": orphaned_relationships,
                "connectivity_ratio": connectivity_ratio,
                "concept_ops_successful": concept_ops_successful,
                "relationship_ops_successful": relationship_ops_successful,
            }
            return _finalize_health_result(self, start, status, message, details)
        except Exception as exc:  # pragma: no cover
            logger.exception("Error during semantic memory health check")
            result = self.create_result(
                HealthCheckStatus.ERROR,
                f"Health check failed with error: {exc}",
                error=str(exc),
                error_type=type(exc).__name__,
            )
            result.execution_time = (time.time() - start) * 1000
            return result


class MemoryHealthMonitor:
    """Coordinates memory-specific registrations with the global health system."""

    def __init__(self) -> None:
        self._memory_systems: dict[str, tuple[object, MemoryTier]] = {}
        self._operation_complexity = {
            "store": 0.8,
            "retrieve": 0.5,
            "forget": 0.3,
            "clear": 0.7,
            "update": 0.6,
            "consolidate": 0.7,
        }

    def register_working_memory(self, memory_system, component_id: str = "working_memory") -> ComponentHealth:
        health = register_component_for_health_tracking(component_id)
        register_health_check(WorkingMemoryHealthCheck(component_id, memory_system))
        self._memory_systems[component_id] = (memory_system, MemoryTier.WORKING)
        return health

    def register_episodic_memory(self, memory_system, component_id: str = "episodic_memory") -> ComponentHealth:
        health = register_component_for_health_tracking(component_id)
        register_health_check(EpisodicMemoryHealthCheck(component_id, memory_system))
        self._memory_systems[component_id] = (memory_system, MemoryTier.EPISODIC)
        return health

    def register_semantic_memory(self, memory_system, component_id: str = "semantic_memory") -> ComponentHealth:
        health = register_component_for_health_tracking(component_id)
        register_health_check(SemanticMemoryHealthCheck(component_id, memory_system))
        self._memory_systems[component_id] = (memory_system, MemoryTier.SEMANTIC)
        return health

    def record_memory_operation(self, component_id: str, operation: str, num_items: int = 1) -> None:
        if component_id not in self._memory_systems:
            logger.warning("Memory component '%s' not registered for health monitoring", component_id)
            return

        base_complexity = self._operation_complexity.get(operation, 0.2)
        complexity = min(1.0, base_complexity * (1 + 0.1 * max(0, num_items - 1)))
        record_cognitive_operation(component_id, operation, complexity)
        if complexity >= 0.5:
            record_cognitive_operation(component_id, operation, min(1.0, complexity))


_memory_health_monitor = MemoryHealthMonitor()


def get_memory_health_monitor() -> MemoryHealthMonitor:
    return _memory_health_monitor


def register_memory_system(
    memory_system,
    memory_type: str | MemoryTier,
    component_id: Optional[str] = None,
) -> ComponentHealth:
    monitor = get_memory_health_monitor()

    if isinstance(memory_type, MemoryTier):
        resolved_tier = memory_type
    else:
        resolved_tier = MemoryTier.from_string(memory_type)

    default_ids = {
        MemoryTier.WORKING: "working_memory",
        MemoryTier.EPISODIC: "episodic_memory",
        MemoryTier.SEMANTIC: "semantic_memory",
    }

    register_map = {
        MemoryTier.WORKING: monitor.register_working_memory,
        MemoryTier.EPISODIC: monitor.register_episodic_memory,
        MemoryTier.SEMANTIC: monitor.register_semantic_memory,
    }

    register_fn = register_map.get(resolved_tier)
    if register_fn is None:  # pragma: no cover - defensive guard for future tiers
        raise ValueError(f"Unknown memory type: {memory_type}")

    resolved_component_id = component_id or default_ids[resolved_tier]
    return register_fn(memory_system, resolved_component_id)


def record_memory_operation(component_id: str, operation: str, num_items: int = 1) -> None:
    get_memory_health_monitor().record_memory_operation(component_id, operation, num_items)
