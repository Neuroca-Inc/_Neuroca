"""Neo4j-backed knowledge graph implementation."""

from __future__ import annotations

import asyncio
from typing import Any, Mapping, MutableMapping, Optional, Sequence

from neuroca.memory.backends.knowledge_graph.base import KnowledgeGraphBackend


class Neo4jKnowledgeGraphBackend(KnowledgeGraphBackend):
    """Persist knowledge graph relationships using a Neo4j connection pool."""

    def __init__(
        self,
        pool: Any,
        *,
        node_label: str = "Memory",
        relationship_label: str = "RELATED_TO",
    ) -> None:
        """Configure the backend with an externally managed connection pool."""
        if pool is None:
            raise ValueError("pool is required for the Neo4j knowledge graph backend")
        self._pool = pool
        self._node_label = node_label
        self._relationship_label = relationship_label

    async def upsert_node(
        self,
        node_id: str,
        *,
        properties: Optional[Mapping[str, Any]] = None,
    ) -> None:
        """Create or update a node representing a memory item."""
        await self._run_query(
            f"MERGE (n:{self._node_label} {{id: $id}}) "
            "SET n += $properties",
            {"id": node_id, "properties": dict(properties or {})},
        )

    async def remove_node(self, node_id: str) -> None:
        """Detach and delete the node identified by *node_id*."""
        await self._run_query(
            f"MATCH (n:{self._node_label} {{id: $id}}) DETACH DELETE n",
            {"id": node_id},
        )

    async def add_relationship(
        self,
        source_id: str,
        target_id: str,
        relationship_type: str,
        *,
        strength: float,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> bool:
        """Persist a relationship between two memory nodes."""
        parameters = {
            "source_id": source_id,
            "target_id": target_id,
            "type": relationship_type,
            "strength": float(strength),
            "metadata": dict(metadata or {}),
        }
        await self._run_query(
            f"MERGE (s:{self._node_label} {{id: $source_id}}) "
            f"MERGE (t:{self._node_label} {{id: $target_id}}) "
            f"MERGE (s)-[r:{self._relationship_label} {{type: $type}}]->(t) "
            "SET r.strength = $strength, r.metadata = $metadata",
            parameters,
        )
        return True

    async def remove_relationship(
        self,
        source_id: str,
        target_id: str,
        relationship_type: Optional[str] = None,
    ) -> bool:
        """Remove relationships between two nodes."""
        query = (
            f"MATCH (s:{self._node_label} {{id: $source_id}})"
            f"-[r:{self._relationship_label}]->"
            f"(t:{self._node_label} {{id: $target_id}})"
        )
        if relationship_type:
            query += " WHERE r.type = $type"
        query += " DELETE r RETURN count(r) AS deleted"

        parameters = {"source_id": source_id, "target_id": target_id}
        if relationship_type:
            parameters["type"] = relationship_type

        records = await self._run_query(query, parameters)
        if not records:
            return False
        deleted = records[0].get("deleted", 0)
        return bool(deleted)

    async def get_related(
        self,
        node_id: str,
        *,
        relationship_type: Optional[str] = None,
        min_strength: float = 0.0,
        limit: int = 10,
    ) -> Sequence[MutableMapping[str, Any]]:
        """Return relationships originating from the supplied node."""
        query = (
            f"MATCH (s:{self._node_label} {{id: $id}})"
            f"-[r:{self._relationship_label}]->(t:{self._node_label}) "
            "WHERE r.strength >= $min_strength"
        )
        parameters: dict[str, Any] = {"id": node_id, "min_strength": float(min_strength)}
        if relationship_type:
            query += " AND r.type = $type"
            parameters["type"] = relationship_type
        query += " RETURN t.id AS target_id, r.type AS relationship_type, "
        query += "r.strength AS strength, coalesce(r.metadata, {}) AS metadata "
        query += "ORDER BY r.strength DESC LIMIT $limit"
        parameters["limit"] = max(limit, 0)

        records = await self._run_query(query, parameters, read_only=True)
        return [dict(record) for record in records]

    async def _run_query(
        self,
        query: str,
        parameters: Mapping[str, Any],
        *,
        read_only: bool = False,
    ) -> Sequence[MutableMapping[str, Any]]:
        """Execute *query* using the configured connection pool."""

        def _execute() -> Sequence[MutableMapping[str, Any]]:
            with self._pool.get_connection() as connection:
                return connection.query(query, dict(parameters), read_only=read_only)

        return await asyncio.to_thread(_execute)
