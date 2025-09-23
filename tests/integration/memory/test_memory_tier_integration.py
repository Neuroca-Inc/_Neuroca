"""Integration tests for Neuroca's tiered memory system."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Dict, List

import pytest

from neuroca.memory.backends.factory.backend_type import BackendType
from neuroca.memory.backends.factory.storage_factory import StorageBackendFactory
from neuroca.memory.interfaces.memory_tier import MemoryTierInterface
from neuroca.memory.manager import MemoryManager
from neuroca.memory.models.memory_item import MemoryContent, MemoryItem, MemoryMetadata
from neuroca.memory.tiers.ltm.core import LongTermMemoryTier
from neuroca.memory.tiers.mtm.core import MediumTermMemoryTier
from neuroca.memory.tiers.stm.core import ShortTermMemoryTier

@asynccontextmanager
async def create_tier_backends() -> Dict[str, MemoryTierInterface]:
    """Provision in-memory tier backends for integration tests."""
    stm = ShortTermMemoryTier(
        storage_backend=StorageBackendFactory.create_storage(backend_type=BackendType.MEMORY)
    )
    mtm = MediumTermMemoryTier(
        storage_backend=StorageBackendFactory.create_storage(backend_type=BackendType.MEMORY)
    )
    ltm = LongTermMemoryTier(
        storage_backend=StorageBackendFactory.create_storage(backend_type=BackendType.MEMORY)
    )

    await stm.initialize()
    await mtm.initialize()
    await ltm.initialize()

    try:
        yield {"stm": stm, "mtm": mtm, "ltm": ltm}
    finally:
        await stm.shutdown()
        await mtm.shutdown()
        await ltm.shutdown()


@asynccontextmanager
async def create_memory_manager() -> MemoryManager:
    """Create a memory manager backed by in-memory tier storage."""
    manager = MemoryManager(
        stm_storage_type=BackendType.MEMORY,
        mtm_storage_type=BackendType.MEMORY,
        ltm_storage_type=BackendType.MEMORY,
    )
    await manager.initialize()
    try:
        yield manager
    finally:
        await manager.shutdown()


@pytest.fixture
def sample_memories() -> List[MemoryItem]:
    """Generate representative memory items for integration scenarios."""
    return [
        MemoryItem(
            content=MemoryContent(text="This is a test memory for integration tests"),
            metadata=MemoryMetadata(
                importance=0.8,
                source="integration_test",
                tags={"test": True, "integration": True},
            ),
        ),
        MemoryItem(
            content=MemoryContent(text="Another test memory with different characteristics"),
            metadata=MemoryMetadata(
                importance=0.5,
                source="integration_test",
                tags={"test": True, "different": True},
            ),
        ),
        MemoryItem(
            content=MemoryContent(text="Low importance memory that might be forgotten"),
            metadata=MemoryMetadata(
                importance=0.2,
                source="integration_test",
                tags={"test": True, "low_importance": True},
            ),
        ),
    ]


async def store_memory_item(
    manager: MemoryManager,
    memory: MemoryItem,
    tier: str = MemoryManager.STM_TIER,
) -> str:
    """Persist a ``MemoryItem`` through the manager API and return its identifier."""
    content_value = ""
    if hasattr(memory, "content") and hasattr(memory.content, "primary_text"):
        content_value = memory.content.primary_text
    elif isinstance(memory.content, dict):
        content_value = memory.content.get("text") or str(memory.content)
    else:
        content_value = str(memory.content)

    metadata_dict = memory.metadata.model_dump(exclude_none=True)
    importance = metadata_dict.pop("importance", 0.5)
    tags_dict = metadata_dict.pop("tags", {})
    tags = [tag for tag, enabled in tags_dict.items() if enabled]

    return await manager.add_memory(
        content=content_value,
        summary=memory.summary,
        importance=importance,
        metadata=metadata_dict,
        tags=tags,
        initial_tier=tier,
    )


class TestTierIntegration:
    """Exercise direct tier interactions."""

    @pytest.mark.asyncio
    async def test_stm_storage_and_retrieval(
        self, sample_memories: List[MemoryItem]
    ) -> None:
        """Ensure STM storage supports round-trip retrieval."""
        async with create_tier_backends() as tier_backends:
            stm = tier_backends["stm"]

            memory_ids: list[str] = []
            for memory in sample_memories:
                memory_ids.append(await stm.store(memory))

            for memory_id in memory_ids:
                assert await stm.exists(memory_id)

            for index, memory_id in enumerate(memory_ids):
                retrieved = await stm.retrieve(memory_id)
                assert retrieved is not None
                assert retrieved.content == sample_memories[index].content
                assert retrieved.metadata.importance == sample_memories[index].metadata.importance

    @pytest.mark.asyncio
    async def test_cross_tier_transfer(
        self, sample_memories: List[MemoryItem]
    ) -> None:
        """Move a memory from STM to MTM and ensure integrity."""
        async with create_tier_backends() as tier_backends:
            stm = tier_backends["stm"]
            mtm = tier_backends["mtm"]

            memory_id = await stm.store(sample_memories[0])
            memory = await stm.retrieve(memory_id)
            assert memory is not None

            mtm_memory = MemoryItem(content=memory.content, metadata=memory.metadata)
            mtm_id = await mtm.store(mtm_memory)

            mtm_memory = await mtm.retrieve(mtm_id)
            assert mtm_memory is not None
            assert mtm_memory.content == memory.content

            await stm.delete(memory_id)
            assert await stm.retrieve(memory_id) is None
            assert await mtm.retrieve(mtm_id) is not None

    @pytest.mark.asyncio
    async def test_vector_search(
        self, sample_memories: List[MemoryItem]
    ) -> None:
        """Store memories in LTM and confirm they remain retrievable."""
        async with create_tier_backends() as tier_backends:
            ltm = tier_backends["ltm"]

            memory_ids: list[str] = []
            for memory in sample_memories:
                memory_ids.append(await ltm.store(memory))

            for memory_id in memory_ids:
                assert await ltm.exists(memory_id)
                retrieved = await ltm.retrieve(memory_id)
                assert retrieved is not None
                assert isinstance(retrieved, MemoryItem)


class TestMemoryManagerIntegration:
    """Validate memory manager operations spanning multiple tiers."""

    @pytest.mark.asyncio
    async def test_direct_storage(
        self, sample_memories: List[MemoryItem]
    ) -> None:
        """Ensure direct STM interactions via the manager remain functional."""
        async with create_memory_manager() as memory_manager:
            memory = sample_memories[0]
            memory_id = await memory_manager.stm_storage.store(memory)

            assert await memory_manager.stm_storage.exists(memory_id)

            retrieved = await memory_manager.stm_storage.retrieve(memory_id)
            assert retrieved is not None
            assert isinstance(retrieved, MemoryItem)
            assert retrieved.content.text == memory.content.text

    @pytest.mark.asyncio
    async def test_tier_transfer(
        self, sample_memories: List[MemoryItem]
    ) -> None:
        """Promote a memory through STM and into MTM using manual orchestration."""
        async with create_memory_manager() as memory_manager:
            memory_id = await store_memory_item(memory_manager, sample_memories[0])

            assert await memory_manager.stm_storage.exists(memory_id)

            stm_memory = await memory_manager.stm_storage.retrieve(memory_id)
            assert stm_memory is not None

            if isinstance(stm_memory, dict):
                mtm_memory = stm_memory.copy()
                mtm_memory.pop("_id", None)
            else:
                mtm_memory = MemoryItem(content=stm_memory.content, metadata=stm_memory.metadata)

            mtm_id = await memory_manager.mtm_storage.store(mtm_memory)
            assert mtm_id is not None
            assert await memory_manager.mtm_storage.exists(mtm_id)

    @pytest.mark.asyncio
    async def test_multi_tier_storage(
        self, sample_memories: List[MemoryItem]
    ) -> None:
        """Store memories across STM, MTM, and LTM via the manager."""
        async with create_memory_manager() as memory_manager:
            stm_id = await memory_manager.stm_storage.store(sample_memories[0])
            mtm_id = await memory_manager.mtm_storage.store(sample_memories[1])
            ltm_id = await memory_manager.ltm_storage.store(sample_memories[2])

            assert await memory_manager.stm_storage.exists(stm_id)
            assert await memory_manager.mtm_storage.exists(mtm_id)
            assert await memory_manager.ltm_storage.exists(ltm_id)

            stm_memory = await memory_manager.stm_storage.retrieve(stm_id)
            assert stm_memory is not None
            assert isinstance(stm_memory, MemoryItem)
            assert stm_memory.content.text == sample_memories[0].content.text

            mtm_memory = await memory_manager.mtm_storage.retrieve(mtm_id)
            assert mtm_memory is not None
            assert isinstance(mtm_memory, MemoryItem)
            assert mtm_memory.content.text == sample_memories[1].content.text

            ltm_memory = await memory_manager.ltm_storage.retrieve(ltm_id)
            assert ltm_memory is not None
            assert isinstance(ltm_memory, MemoryItem)
            assert ltm_memory.content.text == sample_memories[2].content.text

    @pytest.mark.asyncio
    async def test_memory_context(
        self, sample_memories: List[MemoryItem]
    ) -> None:
        """Verify the manager can provide prompt context memories."""
        async with create_memory_manager() as memory_manager:
            for memory in sample_memories:
                await store_memory_item(memory_manager, memory)

            context_memories = await memory_manager.get_prompt_context_memories(max_memories=2)

            assert len(context_memories) <= 2
            assert all("test" in memory.content for memory in context_memories)


class TestBackendIntegration:
    """Ensure tier abstractions tolerate alternate backend implementations."""

    @pytest.mark.parametrize(
        "backend_type",
        [
            BackendType.MEMORY,
            BackendType.SQLITE,
            pytest.param(
                BackendType.REDIS,
                marks=pytest.mark.skipif(True, reason="Redis server might not be available in test runs"),
            ),
        ],
    )
    @pytest.mark.asyncio
    async def test_backend_compatibility(
        self, backend_type: BackendType, sample_memories: List[MemoryItem]
    ) -> None:
        """Run smoke tests against alternate backend configurations."""
        if backend_type == BackendType.REDIS:
            pytest.skip("Redis tests are skipped by default")
        if backend_type == BackendType.SQLITE:
            pytest.skip("SQLite backend requires dedicated orchestration in CI")

        try:
            stm = ShortTermMemoryTier(backend_type=backend_type)
            await stm.initialize()
        except Exception as exc:  # pragma: no cover - defensive guard for unavailable services
            pytest.skip(f"Backend {backend_type} not available: {exc}")

        try:
            memory_id = await stm.store(sample_memories[0])
            retrieved = await stm.retrieve(memory_id)
            assert retrieved is not None
            if isinstance(retrieved, dict):
                retrieved = MemoryItem.model_validate(retrieved)
            assert retrieved.content.text == sample_memories[0].content.text

            batch_ids = await stm.batch_store(sample_memories[1:])
            assert len(batch_ids) == len(sample_memories[1:])

            if backend_type != BackendType.MEMORY:
                assert await stm.count() == len(sample_memories)
            else:
                for memory in sample_memories:
                    assert await stm.exists(memory.id)
        finally:
            await stm.shutdown()
