"""Lightweight semantic-memory implementation for compatibility tests."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, Optional


class RelationshipType(str, Enum):
    """Relationship taxonomy maintained for legacy health checks."""

    IS_A = "is_a"
    HAS_A = "has_a"
    PART_OF = "part_of"
    RELATED_TO = "related_to"
    OPPOSITE_OF = "opposite_of"
    SIMILAR_TO = "similar_to"
    CAUSES = "causes"
    PRECEDES = "precedes"
    LOCATED_IN = "located_in"
    ASSOCIATED_WITH = "associated_with"


@dataclass
class Concept:
    """Simple concept representation used by semantic memory."""

    id: str
    name: str
    description: str = ""
    properties: dict[str, Any] = field(default_factory=dict)

    def update_properties(self, updates: dict[str, Any]) -> None:
        self.properties.update(updates)


@dataclass
class Relationship:
    """Directed edge between two concepts."""

    source_id: str
    target_id: str
    relationship_type: str | RelationshipType
    strength: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def __post_init__(self) -> None:
        if isinstance(self.relationship_type, RelationshipType):
            self.relationship_type = self.relationship_type.value


class SemanticMemory:
    """In-memory knowledge graph capturing concepts and their relationships."""

    def __init__(
        self,
        *,
        concepts: Optional[Iterable[dict[str, Any] | Concept]] = None,
        relationships: Optional[Iterable[dict[str, Any] | Relationship]] = None,
        facts: Optional[dict[str, Any]] = None,
    ) -> None:
        self._concepts: dict[str, Concept] = {}
        self._relationships: dict[str, Relationship] = {}
        self._concept_relationships: dict[str, set[str]] = {}
        self._facts: dict[str, Any] = facts.copy() if facts else {}

        if concepts:
            for concept in concepts:
                self.store(self._ensure_concept(concept))
        if relationships:
            for relationship in relationships:
                self.store(self._ensure_relationship(relationship))

    # ------------------------------------------------------------------
    # Construction helpers
    # ------------------------------------------------------------------
    def _ensure_concept(self, value: dict[str, Any] | Concept) -> Concept:
        if isinstance(value, Concept):
            return value
        concept_id = value.get("id") or str(uuid.uuid4())
        return Concept(
            id=concept_id,
            name=value.get("name", concept_id),
            description=value.get("description", ""),
            properties=self._resolve_properties(value),
        )

    def _resolve_properties(self, value: dict[str, Any]) -> dict[str, Any]:
        """Resolve property payload precedence for concept construction."""

        if value.get("properties") is not None:
            return value["properties"]
        if value.get("attributes") is not None:
            return value["attributes"]
        if value.get("metadata") is not None:
            return value["metadata"]
        return {}

    def _ensure_relationship(self, value: dict[str, Any] | Relationship) -> Relationship:
        if isinstance(value, Relationship):
            return value
        return Relationship(
            source_id=value["source_id"],
            target_id=value["target_id"],
            relationship_type=self._resolve_relationship_type(value),
            strength=float(value.get("strength", 1.0)),
            metadata=value.get("metadata", {}),
            id=value.get("id", str(uuid.uuid4())),
        )

    def _resolve_relationship_type(self, value: dict[str, Any]) -> str:
        """Return the relationship type respecting explicit precedence rules."""

        if "relationship_type" in value:
            return value["relationship_type"]
        if "type" in value:
            return value["type"]
        return RelationshipType.RELATED_TO.value

    # ------------------------------------------------------------------
    # Public factory helpers
    # ------------------------------------------------------------------
    def _create_concept(
        self,
        *,
        id: Optional[str] = None,
        name: str,
        description: str = "",
        properties: Optional[dict[str, Any]] = None,
    ) -> Concept:
        return Concept(id=id or str(uuid.uuid4()), name=name, description=description, properties=properties or {})

    def _create_relationship(
        self,
        *,
        source_id: str,
        target_id: str,
        relationship_type: str | RelationshipType,
        strength: float = 0.5,
        metadata: Optional[dict[str, Any]] = None,
    ) -> Relationship:
        return Relationship(
            source_id=source_id,
            target_id=target_id,
            relationship_type=relationship_type,
            strength=strength,
            metadata=metadata or {},
        )

    # ------------------------------------------------------------------
    # Core operations
    # ------------------------------------------------------------------
    def _is_concept_data(self, item: Any) -> bool:
        if isinstance(item, Concept):
            return True
        if isinstance(item, dict):
            return not ("source_id" in item and "target_id" in item)
        return False

    def _is_relationship_data(self, item: Any) -> bool:
        if isinstance(item, Relationship):
            return True
        if isinstance(item, dict):
            return "source_id" in item and "target_id" in item
        return False

    def store(self, item: Concept | Relationship | dict[str, Any]) -> str:
        if self._is_concept_data(item):
            concept = self._ensure_concept(item)  # type: ignore[arg-type]
            self._concepts[concept.id] = concept
            self._concept_relationships.setdefault(concept.id, set())
            return concept.id

        if self._is_relationship_data(item):
            relationship = self._ensure_relationship(item)  # type: ignore[arg-type]
            if relationship.source_id not in self._concepts or relationship.target_id not in self._concepts:
                raise ValueError("Relationships must reference existing concepts")

            self._relationships[relationship.id] = relationship
            self._concept_relationships.setdefault(relationship.source_id, set()).add(relationship.id)
            self._concept_relationships.setdefault(relationship.target_id, set()).add(relationship.id)
            return relationship.id

        raise ValueError("Item is neither a valid Concept nor Relationship data")

    def get_concept(self, concept_id: str) -> Optional[Concept]:
        return self._concepts.get(concept_id)

    def forget_concept(self, concept_id: str) -> bool:
        if concept_id not in self._concepts:
            return False
        self._concepts.pop(concept_id)
        rel_ids = self._concept_relationships.pop(concept_id, set())
        for rel_id in list(rel_ids):
            self._remove_relationship(rel_id)
        for rel_id in list(self._relationships.keys()):
            rel = self._relationships[rel_id]
            if rel.source_id == concept_id or rel.target_id == concept_id:
                self._remove_relationship(rel_id)
        return True

    def _remove_relationship(self, rel_id: str) -> None:
        relationship = self._relationships.pop(rel_id, None)
        if relationship is None:
            return
        self._concept_relationships.get(relationship.source_id, set()).discard(rel_id)
        self._concept_relationships.get(relationship.target_id, set()).discard(rel_id)

    def retrieve_all_concepts(self) -> list[Concept]:
        return list(self._concepts.values())

    def retrieve_all_relationships(self) -> list[Relationship]:
        return list(self._relationships.values())

    def retrieve_relationships_for_concept(self, concept_id: str) -> list[Relationship]:
        rel_ids = self._concept_relationships.get(concept_id, set())
        return [self._relationships[rel_id] for rel_id in rel_ids if rel_id in self._relationships]

    def clear(self) -> None:
        self._concepts.clear()
        self._relationships.clear()
        self._concept_relationships.clear()
        self._facts.clear()

    # ------------------------------------------------------------------
    # Introspection helpers
    # ------------------------------------------------------------------
    def get_metrics(self) -> dict[str, Any]:
        total_concepts = len(self._concepts)
        total_relationships = len(self._relationships)
        connected_concepts = sum(bool(rels) for rels in self._concept_relationships.values())
        connectivity_ratio = connected_concepts / total_concepts if total_concepts else 0.0
        return {
            "total_concepts": total_concepts,
            "total_relationships": total_relationships,
            "connectivity_ratio": connectivity_ratio,
        }

    def get_statistics(self) -> dict[str, Any]:
        metrics = self.get_metrics()
        metrics.update({
            "facts": len(self._facts),
        })
        return metrics


# Compatibility alias used by API wiring
SemanticMemoryManager = SemanticMemory

__all__ = [
    "Concept",
    "Relationship",
    "RelationshipType",
    "SemanticMemory",
    "SemanticMemoryManager",
]
