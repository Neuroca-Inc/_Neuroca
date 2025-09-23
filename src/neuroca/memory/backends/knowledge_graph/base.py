"""Abstract primitives for knowledge graph storage backends."""

from __future__ import annotations

import abc
from typing import Any, Mapping, MutableMapping, Optional, Sequence


class KnowledgeGraphBackend(abc.ABC):
    """Define the operations required for a knowledge graph backend.

    Concrete implementations persist directed relationships between memory
    identifiers while preserving optional strength and metadata attributes.
    Backends may represent nodes in external services (for example Neo4j) or
    maintain an in-memory representation used during tests and local runs.
    """

    async def initialize(self) -> None:
        """Initialize backend resources.

        Implementations may override this method to establish connections or
        create indexes. The default implementation performs no work.
        """

    async def shutdown(self) -> None:
        """Release backend resources.

        Implementations may override this method to close connections or flush
        buffers. The default implementation performs no work.
        """

    @abc.abstractmethod
    async def upsert_node(
        self,
        node_id: str,
        *,
        properties: Optional[Mapping[str, Any]] = None,
    ) -> None:
        """Ensure a node exists in the knowledge graph."""

    @abc.abstractmethod
    async def remove_node(self, node_id: str) -> None:
        """Remove a node and its relationships from the graph."""

    @abc.abstractmethod
    async def add_relationship(
        self,
        source_id: str,
        target_id: str,
        relationship_type: str,
        *,
        strength: float,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> bool:
        """Create or update a relationship between two nodes."""

    @abc.abstractmethod
    async def remove_relationship(
        self,
        source_id: str,
        target_id: str,
        relationship_type: Optional[str] = None,
    ) -> bool:
        """Remove relationships between two nodes."""

    @abc.abstractmethod
    async def get_related(
        self,
        node_id: str,
        *,
        relationship_type: Optional[str] = None,
        min_strength: float = 0.0,
        limit: int = 10,
    ) -> Sequence[MutableMapping[str, Any]]:
        """Return related nodes and relationship metadata for *node_id*."""
