"""Tests for the LTM relationship component metadata handling."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Optional

import pytest

from neuroca.memory.models.memory_item import MemoryContent, MemoryItem, MemoryMetadata
from neuroca.memory.tiers.ltm.components.relationship import LTMRelationship


class _StubBackend:
    """Backend stub exposing the minimal retrieval surface."""

    def __init__(self, data: Dict[str, Dict[str, Any]]) -> None:
        self._data = data

    async def retrieve(self, memory_id: str) -> Dict[str, Any] | None:
        stored = self._data.get(memory_id)
        return deepcopy(stored) if stored is not None else None


class _StubLifecycle:
    """Lifecycle stub tracking relationship map updates."""

    def __init__(self) -> None:
        self.updated: list[tuple[str, str, float]] = []

    def update_relationship(self, source_id: str, target_id: str, strength: float) -> None:
        self.updated.append((source_id, target_id, strength))

    def remove_memory(self, memory_id: str) -> None:  # pragma: no cover - unused in test
        del memory_id

    def get_relationship_map(self) -> Dict[str, Dict[str, float]]:  # pragma: no cover - unused
        return {}


class _StubUpdater:
    """Callable that records metadata updates applied by the component."""

    def __init__(self, backend_data: Dict[str, Dict[str, Any]]) -> None:
        self.backend_data = backend_data
        self.calls: list[tuple[str, Dict[str, Any]]] = []

    async def __call__(self, memory_id: str, *, metadata: Dict[str, Any]) -> bool:
        self.calls.append((memory_id, metadata))
        self.backend_data[memory_id]["metadata"]["tags"] = deepcopy(metadata)
        return True


class _StubGraphBackend:
    """In-memory graph backend stub recording interactions."""

    def __init__(self) -> None:
        self.upserted: list[str] = []
        self.added: list[tuple[str, str, str, float, Dict[str, Any]]] = []
        self.removed: list[tuple[str, str, Optional[str]]] = []
        self.removed_nodes: list[str] = []
        self.related_results: list[Dict[str, Any]] = []

    async def upsert_node(self, node_id: str, *, properties: Dict[str, Any] | None = None) -> None:
        self.upserted.append(node_id)

    async def remove_node(self, node_id: str) -> None:
        self.removed_nodes.append(node_id)

    async def add_relationship(
        self,
        source_id: str,
        target_id: str,
        relationship_type: str,
        *,
        strength: float,
        metadata: Dict[str, Any] | None = None,
    ) -> bool:
        self.added.append((source_id, target_id, relationship_type, strength, dict(metadata or {})))
        return True

    async def remove_relationship(
        self,
        source_id: str,
        target_id: str,
        relationship_type: Optional[str] = None,
    ) -> bool:
        self.removed.append((source_id, target_id, relationship_type))
        return True

    async def get_related(
        self,
        node_id: str,
        *,
        relationship_type: Optional[str] = None,
        min_strength: float = 0.0,
        limit: int = 10,
    ) -> list[Dict[str, Any]]:
        del node_id, relationship_type, min_strength, limit
        return list(self.related_results)


@pytest.mark.asyncio
async def test_add_relationship_persists_metadata_on_both_memories() -> None:
    source = MemoryItem(
        id="source", content=MemoryContent(text="source"), metadata=MemoryMetadata(tags={})
    )
    target = MemoryItem(
        id="target", content=MemoryContent(text="target"), metadata=MemoryMetadata(tags={})
    )

    backend_data = {
        source.id: source.model_dump(),
        target.id: target.model_dump(),
    }

    backend = _StubBackend(backend_data)
    lifecycle = _StubLifecycle()
    updater = _StubUpdater(backend_data)
    graph_backend = _StubGraphBackend()

    relationship = LTMRelationship("ltm")
    relationship.configure(
        lifecycle=lifecycle,
        backend=backend,
        update_func=updater,
        config={},
        graph_backend=graph_backend,
    )

    metadata_payload = {"weight": 0.6, "context": "summary"}

    result = await relationship.add_relationship(
        source.id,
        target.id,
        relationship_type="semantic",
        strength=0.8,
        metadata=metadata_payload,
        bidirectional=True,
    )

    assert result is True
    assert lifecycle.updated == [("source", "target", 0.8), ("target", "source", 0.8)]

    assert graph_backend.upserted == ["source", "target"]
    assert graph_backend.added == [
        ("source", "target", "semantic", 0.8, metadata_payload),
        ("target", "source", "semantic", 0.8, metadata_payload),
    ]

    source_relationships = backend_data[source.id]["metadata"]["tags"]["relationships"]
    target_relationships = backend_data[target.id]["metadata"]["tags"]["relationships"]

    assert source_relationships[target.id]["metadata"] == metadata_payload
    assert target_relationships[source.id]["metadata"] == metadata_payload


@pytest.mark.asyncio
async def test_remove_relationship_invokes_graph_backend() -> None:
    source = MemoryItem(
        id="source", content=MemoryContent(text="s"), metadata=MemoryMetadata(tags={})
    )
    target = MemoryItem(
        id="target", content=MemoryContent(text="t"), metadata=MemoryMetadata(tags={})
    )

    backend_data = {
        source.id: source.model_dump(),
        target.id: target.model_dump(),
    }

    backend = _StubBackend(backend_data)
    lifecycle = _StubLifecycle()
    updater = _StubUpdater(backend_data)
    graph_backend = _StubGraphBackend()

    relationship = LTMRelationship("ltm")
    relationship.configure(
        lifecycle=lifecycle,
        backend=backend,
        update_func=updater,
        config={},
        graph_backend=graph_backend,
    )

    await relationship.add_relationship(source.id, target.id, "semantic")
    await relationship.remove_relationship(source.id, target.id, bidirectional=True)

    assert graph_backend.removed == [
        ("source", "target", None),
        ("target", "source", None),
    ]
    assert backend_data[source.id]["metadata"]["tags"]["relationships"] == {}
    assert backend_data[target.id]["metadata"]["tags"]["relationships"] == {}


@pytest.mark.asyncio
async def test_get_related_memories_returns_serialised_payloads() -> None:
    anchor = MemoryItem(
        id="anchor", content=MemoryContent(text="a"), metadata=MemoryMetadata(tags={})
    )
    related = MemoryItem(
        id="peer", content=MemoryContent(text="b"), metadata=MemoryMetadata(tags={})
    )

    backend_data = {
        anchor.id: anchor.model_dump(),
        related.id: related.model_dump(),
    }

    backend = _StubBackend(backend_data)
    lifecycle = _StubLifecycle()
    updater = _StubUpdater(backend_data)
    graph_backend = _StubGraphBackend()
    graph_backend.related_results = [
        {
            "target_id": related.id,
            "relationship_type": "semantic",
            "strength": 0.9,
            "metadata": {"edge": True},
        }
    ]

    relationship = LTMRelationship("ltm")
    relationship.configure(
        lifecycle=lifecycle,
        backend=backend,
        update_func=updater,
        config={},
        graph_backend=graph_backend,
    )

    results = await relationship.get_related_memories(anchor.id, limit=5)

    assert results == [
        {
            **related.model_dump(),
            "_relationship": {
                "type": "semantic",
                "strength": 0.9,
                "metadata": {"edge": True},
            },
        }
    ]


@pytest.mark.asyncio
async def test_register_and_cleanup_delegate_to_graph_backend() -> None:
    memory = MemoryItem(
        id="memory", content=MemoryContent(text="content"), metadata=MemoryMetadata(tags={})
    )

    backend_data = {memory.id: memory.model_dump()}
    backend = _StubBackend(backend_data)
    lifecycle = _StubLifecycle()
    updater = _StubUpdater(backend_data)
    graph_backend = _StubGraphBackend()

    relationship = LTMRelationship("ltm")
    relationship.configure(
        lifecycle=lifecycle,
        backend=backend,
        update_func=updater,
        config={},
        graph_backend=graph_backend,
    )

    await relationship.register_memory(memory)
    await relationship.cleanup_memory(memory.id)

    assert graph_backend.upserted == [memory.id]
    assert graph_backend.removed_nodes == [memory.id]
