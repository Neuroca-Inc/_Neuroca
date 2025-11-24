"""Unit tests for the MemoryManager relationship operations."""

from __future__ import annotations

from typing import Any, Dict, List

import pytest

from neuroca.memory.manager.memory_manager import MemoryManager
from neuroca.memory.models.memory_item import MemoryContent, MemoryItem, MemoryMetadata
from neuroca.memory.exceptions import MemoryManagerOperationError


class _StubTier:
    """Lightweight tier stub satisfying the manager's lifecycle hooks."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.config: Dict[str, Any] = {}

    async def initialize(self) -> None:  # pragma: no cover - trivial stub
        return None

    async def shutdown(self) -> None:  # pragma: no cover - trivial stub
        return None

    async def count(self, *_args: Any, **_kwargs: Any) -> int:
        return 0


class _StubLtm(_StubTier):
    """Stubbed LTM tier that records relationship interactions."""

    def __init__(self) -> None:
        super().__init__("ltm")
        self.add_calls: List[Dict[str, Any]] = []
        self.remove_calls: List[Dict[str, Any]] = []
        self.related_requests: List[Dict[str, Any]] = []
        self.related_results: List[Dict[str, Any]] = []
        self.catalogue: Dict[str, str] = {"semantic": "Semantic link"}
        self.should_add = True
        self.should_remove = True

    async def add_relationship(
        self,
        source_id: str,
        target_id: str,
        relationship_type: str,
        strength: float = 0.5,
        bidirectional: bool = True,
        metadata: Dict[str, Any] | None = None,
    ) -> bool:
        self.add_calls.append(
            {
                "source_id": source_id,
                "target_id": target_id,
                "relationship_type": relationship_type,
                "strength": strength,
                "bidirectional": bidirectional,
                "metadata": metadata,
            }
        )
        return self.should_add

    async def remove_relationship(
        self,
        source_id: str,
        target_id: str,
        bidirectional: bool = True,
    ) -> bool:
        self.remove_calls.append(
            {
                "source_id": source_id,
                "target_id": target_id,
                "bidirectional": bidirectional,
            }
        )
        return self.should_remove

    async def get_related_memories(
        self,
        memory_id: str,
        relationship_type: str | None = None,
        min_strength: float = 0.0,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        self.related_requests.append(
            {
                "memory_id": memory_id,
                "relationship_type": relationship_type,
                "min_strength": min_strength,
                "limit": limit,
            }
        )
        return list(self.related_results)

    async def get_relationship_types(self) -> Dict[str, str]:
        return dict(self.catalogue)


@pytest.mark.asyncio
async def test_add_relationship_normalizes_type_and_metadata() -> None:
    stm = _StubTier("stm")
    mtm = _StubTier("mtm")
    ltm = _StubLtm()
    manager = MemoryManager(
        config={"maintenance_interval": 0, "resource_limits": {}},
        stm=stm,
        mtm=mtm,
        ltm=ltm,
    )

    await manager.initialize()
    try:
        await manager.add_relationship(
            "source",
            "target",
            "Semantic",
            strength=0.75,
            bidirectional=False,
            metadata={"weight": 0.9},
        )
    finally:
        await manager.shutdown()

    assert ltm.add_calls == [
        {
            "source_id": "source",
            "target_id": "target",
            "relationship_type": "semantic",
            "strength": 0.75,
            "bidirectional": False,
            "metadata": {"weight": 0.9},
        }
    ]


@pytest.mark.asyncio
async def test_add_relationship_rejects_non_mapping_metadata() -> None:
    manager = MemoryManager(
        config={"maintenance_interval": 0, "resource_limits": {}},
        stm=_StubTier("stm"),
        mtm=_StubTier("mtm"),
        ltm=_StubLtm(),
    )

    await manager.initialize()
    try:
        with pytest.raises(MemoryManagerOperationError):
            await manager.add_relationship("a", "b", "semantic", metadata=["invalid"])
    finally:
        await manager.shutdown()


@pytest.mark.asyncio
async def test_add_relationship_raises_when_backend_reports_failure() -> None:
    ltm = _StubLtm()
    ltm.should_add = False
    manager = MemoryManager(
        config={"maintenance_interval": 0, "resource_limits": {}},
        stm=_StubTier("stm"),
        mtm=_StubTier("mtm"),
        ltm=ltm,
    )

    await manager.initialize()
    try:
        with pytest.raises(MemoryManagerOperationError):
            await manager.add_relationship("source", "target", "semantic")
    finally:
        await manager.shutdown()


@pytest.mark.asyncio
async def test_remove_relationship_propagates_backend_result() -> None:
    ltm = _StubLtm()
    manager = MemoryManager(
        config={"maintenance_interval": 0, "resource_limits": {}},
        stm=_StubTier("stm"),
        mtm=_StubTier("mtm"),
        ltm=ltm,
    )

    await manager.initialize()
    try:
        assert await manager.remove_relationship("one", "two") is True
        ltm.should_remove = False
        with pytest.raises(MemoryManagerOperationError):
            await manager.remove_relationship("one", "two")
    finally:
        await manager.shutdown()

    assert ltm.remove_calls == [
        {"source_id": "one", "target_id": "two", "bidirectional": True},
        {"source_id": "one", "target_id": "two", "bidirectional": True},
    ]


@pytest.mark.asyncio
async def test_get_related_memories_wraps_payloads() -> None:
    ltm = _StubLtm()
    related_item = MemoryItem(
        id="rel-1",
        content=MemoryContent(text="linked"),
        metadata=MemoryMetadata(tags={}),
    )
    ltm.related_results = [
        {
            **related_item.model_dump(),
            "_relationship": {
                "type": "semantic",
                "strength": 0.8,
                "metadata": {"weight": 0.4},
            },
        }
    ]

    manager = MemoryManager(
        config={"maintenance_interval": 0, "resource_limits": {}},
        stm=_StubTier("stm"),
        mtm=_StubTier("mtm"),
        ltm=ltm,
    )

    await manager.initialize()
    try:
        results = await manager.get_related_memories("anchor", relationship_type="Semantic", min_strength=0.1, limit=5)
    finally:
        await manager.shutdown()

    assert ltm.related_requests == [
        {
            "memory_id": "anchor",
            "relationship_type": "semantic",
            "min_strength": 0.1,
            "limit": 5,
        }
    ]
    assert len(results) == 1
    payload = results[0]
    assert payload["tier"] == MemoryManager.LTM_TIER
    assert isinstance(payload["memory"], MemoryItem)
    assert payload["memory"].id == "rel-1"
    assert payload["relationship"] == {
        "type": "semantic",
        "strength": 0.8,
        "metadata": {"weight": 0.4},
    }


@pytest.mark.asyncio
async def test_list_relationship_types_uses_ltm_catalogue() -> None:
    ltm = _StubLtm()
    ltm.catalogue = {"semantic": "Semantic", "causal": "Causal chain"}
    manager = MemoryManager(
        config={"maintenance_interval": 0, "resource_limits": {}},
        stm=_StubTier("stm"),
        mtm=_StubTier("mtm"),
        ltm=ltm,
    )

    await manager.initialize()
    try:
        catalogue = await manager.list_relationship_types()
    finally:
        await manager.shutdown()

    assert catalogue == {"semantic": "Semantic", "causal": "Causal chain"}
