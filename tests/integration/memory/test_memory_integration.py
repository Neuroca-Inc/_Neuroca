"""Integration coverage for storage backends and tier orchestration."""

from __future__ import annotations

import uuid

import pytest

from neuroca.memory.backends.factory import BackendType, MemoryTier, StorageBackendFactory
from neuroca.memory.manager import MemoryManager
from neuroca.memory.models.memory_item import MemoryContent, MemoryItem, MemoryMetadata


@pytest.mark.asyncio
@pytest.mark.parametrize("backend_type", [BackendType.MEMORY, BackendType.SQLITE])
async def test_storage_backend_round_trip_across_backends(tmp_path, backend_type):
    """Persist and retrieve memories using each supported backend implementation."""

    instance_suffix = uuid.uuid4().hex
    backend_config: dict[str, object] = {}
    if backend_type is BackendType.SQLITE:
        db_path = tmp_path / f"{backend_type.value}_{instance_suffix}.db"
        backend_config = {"sqlite": {"connection": {"database_path": str(db_path)}}}

    backend = StorageBackendFactory.create_storage(
        tier=MemoryTier.STM,
        backend_type=backend_type,
        config=backend_config,
        use_existing=False,
        instance_name=f"integration_{backend_type.value}_{instance_suffix}",
    )
    await backend.initialize()

    try:
        payload = MemoryItem(
            content=MemoryContent(text="Backend integration check"),
            metadata=MemoryMetadata(importance=0.73, tags={"suite": "integration"}),
        )
        memory_id = await backend.store(payload)

        assert await backend.exists(memory_id)

        fetched = await backend.retrieve(memory_id)
        assert isinstance(fetched, MemoryItem)
        assert fetched.content.primary_text == "Backend integration check"

        await backend.delete(memory_id)
        assert not await backend.exists(memory_id)
    finally:
        await backend.shutdown()


@pytest.mark.asyncio
async def test_memory_manager_sqlite_integration_flow():
    """Exercise the memory manager lifecycle when every tier uses SQLite storage."""

    StorageBackendFactory._instances.clear()
    manager = MemoryManager(
        stm_storage_type=BackendType.SQLITE,
        mtm_storage_type=BackendType.SQLITE,
        ltm_storage_type=BackendType.SQLITE,
        backend_config={"sqlite": {"connection": {"database_path": ":memory:"}}},
        config={
            "monitoring": {
                "metrics": {"enabled": False},
                "events": {"enabled": False},
            }
        },
    )
    await manager.initialize()

    try:
        memory_id = await manager.add_memory(
            content="SQLite backed memory",
            summary="integration flow",
            importance=0.82,
            metadata={"source": "integration-suite"},
            tags=["integration", "sqlite"],
        )

        stm_item = await manager.stm_storage.retrieve(memory_id)
        assert stm_item is not None
        assert getattr(stm_item.metadata, "tier", MemoryManager.STM_TIER) == MemoryManager.STM_TIER

        mtm_item = await manager.transfer_memory(memory_id, MemoryManager.MTM_TIER)
        assert mtm_item.metadata.tier == MemoryManager.MTM_TIER

        ltm_item = await manager.transfer_memory(memory_id, MemoryManager.LTM_TIER)
        assert ltm_item.metadata.tier == MemoryManager.LTM_TIER

        stored_ltm = await manager.ltm_storage.retrieve(memory_id)
        assert stored_ltm is not None
        assert stored_ltm.metadata.tier == MemoryManager.LTM_TIER
    finally:
        await manager.shutdown()
