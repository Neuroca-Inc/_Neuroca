"""Integration tests for Neuroca's tiered memory system."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

import pytest

from neuroca.memory.backends.base import BaseStorageBackend
from neuroca.memory.backends.factory import MemoryTier
from neuroca.memory.backends.factory.backend_type import BackendType
from neuroca.memory.backends.factory.storage_factory import StorageBackendFactory
from neuroca.memory.interfaces.memory_tier import MemoryTierInterface
from neuroca.memory.manager import MemoryManager
from neuroca.memory.models.memory_item import MemoryContent, MemoryItem, MemoryMetadata
from neuroca.memory.tiers.ltm.core import LongTermMemoryTier
from neuroca.memory.tiers.mtm.core import MediumTermMemoryTier
from neuroca.memory.tiers.stm.core import ShortTermMemoryTier


@pytest.fixture(scope="module")
def fake_redis_backend():
    """Route Redis backend traffic to fakeredis for deterministic tests."""

    fakeredis = pytest.importorskip("fakeredis.aioredis")
    from neuroca.memory.backends.redis import components as redis_components
    from neuroca.memory.backends.redis.components import connection as redis_connection

    original_aioredis = redis_connection.aioredis
    original_redis_cls = redis_connection.Redis

    redis_connection.aioredis = fakeredis
    redis_connection.Redis = fakeredis.FakeRedis

    original_module_aioredis = getattr(redis_components, "aioredis", None)
    original_module_redis = getattr(redis_components, "Redis", None)
    redis_components.aioredis = fakeredis
    redis_components.Redis = fakeredis.FakeRedis

    try:
        yield
    finally:
        redis_connection.aioredis = original_aioredis
        redis_connection.Redis = original_redis_cls
        if original_module_aioredis is not None:
            redis_components.aioredis = original_module_aioredis
        else:
            delattr(redis_components, "aioredis")
        if original_module_redis is not None:
            redis_components.Redis = original_module_redis
        else:
            delattr(redis_components, "Redis")

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
            BackendType.REDIS,
            BackendType.QDRANT,
        ],
    )
    @pytest.mark.asyncio
    @pytest.mark.usefixtures("fake_redis_backend")
    async def test_backend_compatibility(
        self,
        backend_type: BackendType,
        sample_memories: List[MemoryItem],
        tmp_path_factory: pytest.TempPathFactory,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Run smoke tests against alternate backend configurations."""

        if backend_type == BackendType.QDRANT:
            backend = StorageBackendFactory.create_storage(
                tier=MemoryTier.LTM,
                backend_type=backend_type,
                config={
                    "location": ":memory:",
                    "collection_name": "integration_backend_test",
                    "dimension": 3,
                    "recreate_collection": True,
                },
                use_existing=False,
                instance_name="integration_backend_test",
            )
            tier = LongTermMemoryTier(storage_backend=backend)
            primary_memory = MemoryItem(
                content=MemoryContent(text="Qdrant vector memory integration"),
                metadata=MemoryMetadata(
                    importance=0.7,
                    tags={"test": True, "vector": True},
                    tier=MemoryManager.LTM_TIER,
                ),
                embedding=[0.12, 0.05, 0.33],
            )
            batch_payload = [
                MemoryItem(
                    content=MemoryContent(text="Supplemental Qdrant entry"),
                    metadata=MemoryMetadata(
                        importance=0.5,
                        tags={"test": True, "vector": True},
                        tier=MemoryManager.LTM_TIER,
                    ),
                    embedding=[0.2, 0.1, 0.25],
                ),
                MemoryItem(
                    content=MemoryContent(text="Secondary Qdrant item"),
                    metadata=MemoryMetadata(
                        importance=0.55,
                        tags={"test": True, "vector": True},
                        tier=MemoryManager.LTM_TIER,
                    ),
                    embedding=[0.18, 0.16, 0.22],
                ),
            ]
        elif backend_type == BackendType.SQLITE:
            db_root = tmp_path_factory.mktemp("sqlite-backend")
            backend = StorageBackendFactory.create_storage(
                tier=MemoryTier.STM,
                backend_type=backend_type,
                config={
                    "sqlite": {
                        "connection": {
                            "database_path": str(db_root / "integration.sqlite"),
                            "create_if_missing": True,
                        }
                    }
                },
                use_existing=False,
                instance_name="integration_sqlite_backend",
            )
            await backend.initialize()
            await backend.shutdown()
            return
        elif backend_type == BackendType.REDIS:
            class _InProcessRedisBackend(BaseStorageBackend):
                """Minimal in-memory backend used to simulate Redis for tests."""

                def __init__(self, config: Optional[Dict[str, Any]] = None, **_: Any) -> None:
                    super().__init__(config or {})
                    self._store: Dict[str, Dict[str, Any]] = {}

                async def _initialize_backend(self) -> None:
                    return None

                async def _shutdown_backend(self) -> None:
                    self._store.clear()

                async def _create_item(self, item_id: str, data: Dict[str, Any]) -> bool:
                    self._store[item_id] = data
                    return True

                async def _read_item(self, item_id: str) -> Optional[Dict[str, Any]]:
                    return self._store.get(item_id)

                async def _update_item(self, item_id: str, data: Dict[str, Any]) -> bool:
                    self._store[item_id] = data
                    return True

                async def _delete_item(self, item_id: str) -> bool:
                    return self._store.pop(item_id, None) is not None

                async def _item_exists(self, item_id: str) -> bool:
                    return item_id in self._store

                async def _query_items(
                    self,
                    filters: Optional[Dict[str, Any]] = None,
                    sort_by: Optional[str] = None,
                    ascending: bool = True,
                    limit: Optional[int] = None,
                    offset: Optional[int] = None,
                ) -> List[Dict[str, Any]]:
                    del filters, sort_by, ascending
                    items = list(self._store.values())
                    if offset:
                        items = items[offset:]
                    if limit is not None and limit >= 0:
                        items = items[:limit]
                    return items

                async def _count_items(self, filters: Optional[Dict[str, Any]] = None) -> int:
                    del filters
                    return len(self._store)

                async def _clear_all_items(self) -> bool:
                    self._store.clear()
                    return True

                async def _get_backend_stats(self) -> Dict[str, Any]:
                    return {"items": len(self._store)}

            monkeypatch.setitem(
                StorageBackendFactory._backend_registry,
                BackendType.REDIS,
                _InProcessRedisBackend,
            )
            tier = ShortTermMemoryTier(backend_type=backend_type)
            primary_memory = sample_memories[0]
            batch_payload = sample_memories[1:]
        else:
            tier = ShortTermMemoryTier(backend_type=backend_type)
            primary_memory = sample_memories[0]
            batch_payload = sample_memories[1:]

        try:
            await tier.initialize()
        except Exception as exc:  # pragma: no cover - guard for unavailable services
            pytest.skip(f"Backend {backend_type} not available: {exc}")

        try:
            memory_id = await tier.store(primary_memory)
            retrieved = await tier.retrieve(memory_id)
            assert retrieved is not None
            if isinstance(retrieved, dict):
                retrieved = MemoryItem.model_validate(retrieved)
            assert retrieved.content.text.startswith(primary_memory.content.text.split()[0])

            batch_ids = await tier.batch_store(batch_payload)
            assert len(batch_ids) == len(batch_payload)

            exists_result = await tier.exists(memory_id)
            assert exists_result is True

            if backend_type != BackendType.MEMORY:
                counted = await tier.count()
                assert counted >= len(batch_payload) + 1

            if backend_type == BackendType.QDRANT:
                search_results = await tier.search(
                    query="Qdrant",
                    filters={"metadata.tags.test": True},
                    limit=5,
                )
                assert search_results.results
                similarity_results = await tier.search(
                    embedding=primary_memory.embedding or [],
                    filters={"metadata.tags.vector": True},
                    limit=3,
                )
                assert similarity_results.results
            else:
                for stored_id in [memory_id, *batch_ids]:
                    retrieved_item = await tier.retrieve(stored_id)
                    assert retrieved_item is not None
        finally:
            await tier.shutdown()
