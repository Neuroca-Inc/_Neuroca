"""In-memory knowledge graph backend implementation."""

from __future__ import annotations

from typing import Any, Dict, Mapping, MutableMapping, Optional, Sequence

from neuroca.memory.backends.knowledge_graph.base import KnowledgeGraphBackend


class InMemoryKnowledgeGraphBackend(KnowledgeGraphBackend):
    """Maintain knowledge graph relationships inside the current process."""

    def __init__(self) -> None:
        """Initialise the in-memory node and edge registries."""
        self._nodes: Dict[str, Dict[str, Any]] = {}
        self._edges: Dict[str, Dict[str, Dict[str, Dict[str, Any]]]] = {}

    async def upsert_node(
        self,
        node_id: str,
        *,
        properties: Optional[Mapping[str, Any]] = None,
    ) -> None:
        """Insert or update the node identified by *node_id*."""
        if properties is None:
            properties = {}
        self._nodes[node_id] = dict(properties)

    async def remove_node(self, node_id: str) -> None:
        """Remove *node_id* and detach any relationships."""
        self._nodes.pop(node_id, None)
        self._edges.pop(node_id, None)
        for source_id, buckets in list(self._edges.items()):
            for rel_type, targets in list(buckets.items()):
                targets.pop(node_id, None)
                if not targets:
                    buckets.pop(rel_type, None)
            if not buckets:
                self._edges.pop(source_id, None)

    async def add_relationship(
        self,
        source_id: str,
        target_id: str,
        relationship_type: str,
        *,
        strength: float,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> bool:
        """Persist or update a relationship between two nodes."""
        await self.upsert_node(source_id)
        await self.upsert_node(target_id)

        bucket = self._edges.setdefault(source_id, {}).setdefault(relationship_type, {})
        payload: Dict[str, Any] = {
            "relationship_type": relationship_type,
            "target_id": target_id,
            "strength": float(strength),
            "metadata": dict(metadata or {}),
        }
        bucket[target_id] = payload
        return True

    async def remove_relationship(
        self,
        source_id: str,
        target_id: str,
        relationship_type: Optional[str] = None,
    ) -> bool:
        """Remove relationships between *source_id* and *target_id*."""
        buckets = self._edges.get(source_id)
        if not buckets:
            return False

        removed = False
        relationship_types = [relationship_type] if relationship_type else list(buckets.keys())
        for rel_type in relationship_types:
            targets = buckets.get(rel_type)
            if not targets:
                continue
            removed = targets.pop(target_id, None) is not None or removed
            if not targets:
                buckets.pop(rel_type, None)
        if not buckets:
            self._edges.pop(source_id, None)
        return removed

    async def get_related(
        self,
        node_id: str,
        *,
        relationship_type: Optional[str] = None,
        min_strength: float = 0.0,
        limit: int = 10,
    ) -> Sequence[MutableMapping[str, Any]]:
        """Return relationships originating from *node_id*."""
        buckets = self._edges.get(node_id)
        if not buckets:
            return []

        results: list[MutableMapping[str, Any]] = []
        types_to_check = [relationship_type] if relationship_type else list(buckets.keys())
        for rel_type in types_to_check:
            targets = buckets.get(rel_type)
            if not targets:
                continue
            for payload in targets.values():
                if payload["strength"] < min_strength:
                    continue
                results.append(dict(payload))

        results.sort(key=lambda entry: entry.get("strength", 0.0), reverse=True)
        return results[: max(limit, 0)]
