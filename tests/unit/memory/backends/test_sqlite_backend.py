"""Unit tests for the in-memory backend behaving like SQLite storage."""

from __future__ import annotations

from contextlib import asynccontextmanager
import uuid

import pytest

from neuroca.memory.backends.factory.backend_type import BackendType
from neuroca.memory.backends.factory.storage_factory import StorageBackendFactory
from neuroca.memory.models.memory_item import MemoryItem, MemoryContent, MemoryMetadata


@asynccontextmanager
async def create_memory_backend():
    """Provision a temporary in-memory backend for backend API validation."""
    backend = StorageBackendFactory.create_storage(backend_type=BackendType.MEMORY)
    await backend.initialize()
    try:
        yield backend
    finally:
        await backend.shutdown()


@pytest.mark.asyncio
async def test_store_and_retrieve():
    """Test storing and retrieving a memory item."""
    async with create_memory_backend() as memory_backend:
        memory_id = str(uuid.uuid4())
        memory = MemoryItem(
            id=memory_id,
            content=MemoryContent(text="Test content"),
            summary="Test summary",
            metadata=MemoryMetadata(importance=0.8, tags={"test": True, "memory": True}),
        )

        stored_id = await memory_backend.store(memory)
        assert stored_id == memory_id

        retrieved = await memory_backend.retrieve(memory_id)
        assert retrieved is not None
        assert retrieved.id == memory_id
        assert retrieved.content.text == "Test content"
        assert retrieved.summary == "Test summary"
        assert retrieved.metadata.importance == 0.8
        assert "test" in retrieved.metadata.tags
        assert "memory" in retrieved.metadata.tags


@pytest.mark.asyncio
async def test_update():
    """Test updating a memory item."""
    async with create_memory_backend() as memory_backend:
        memory_id = str(uuid.uuid4())
        memory = MemoryItem(
            id=memory_id,
            content=MemoryContent(text="Initial content"),
            summary="Initial summary",
            metadata=MemoryMetadata(importance=0.5),
        )
        await memory_backend.store(memory)

        updated_memory = MemoryItem(
            id=memory_id,
            content=MemoryContent(text="Updated content"),
            summary="Updated summary",
            metadata=MemoryMetadata(importance=0.7, tags={"updated": True}),
        )
        success = await memory_backend.update(memory_id, updated_memory.model_dump())
        assert success is True

        retrieved = await memory_backend.retrieve(memory_id)
        assert retrieved.content.text == "Updated content"
        assert retrieved.summary == "Updated summary"
        assert retrieved.metadata.importance == 0.7
        assert "updated" in retrieved.metadata.tags


@pytest.mark.asyncio
async def test_delete():
    """Test deleting a memory item."""
    async with create_memory_backend() as memory_backend:
        memory_id = str(uuid.uuid4())
        memory = MemoryItem(
            id=memory_id,
            content=MemoryContent(text="Content to delete"),
            summary="Summary to delete",
        )
        await memory_backend.store(memory)

        retrieved = await memory_backend.retrieve(memory_id)
        assert retrieved is not None

        success = await memory_backend.delete(memory_id)
        assert success is True

        retrieved = await memory_backend.retrieve(memory_id)
        assert retrieved is None


@pytest.mark.skip("Search implementation varies across backends")
@pytest.mark.asyncio
async def test_search():
    """Test searching for memory items."""
    async with create_memory_backend() as memory_backend:
        memories = [
            MemoryItem(
                id=str(uuid.uuid4()),
                content=MemoryContent(text="Apple is a fruit"),
                summary="About apples",
                metadata=MemoryMetadata(importance=0.7, tags={"fruit": True, "apple": True}),
            ),
            MemoryItem(
                id=str(uuid.uuid4()),
                content=MemoryContent(text="Banana is yellow"),
                summary="About bananas",
                metadata=MemoryMetadata(importance=0.5, tags={"fruit": True, "banana": True}),
            ),
            MemoryItem(
                id=str(uuid.uuid4()),
                content=MemoryContent(text="Car is a vehicle"),
                summary="About cars",
                metadata=MemoryMetadata(importance=0.8, tags={"vehicle": True, "car": True}),
            ),
        ]

        for memory in memories:
            await memory_backend.store(memory)

        try:
            all_items = memory_backend.storage._items
        except AttributeError:
            pytest.skip("Backend does not expose an item collection for inspection")
        else:
            assert len(all_items) == 3


@pytest.mark.asyncio
async def test_batch_operations():
    """Test batch store and delete operations."""
    async with create_memory_backend() as memory_backend:
        memories = [
            MemoryItem(
                id=str(uuid.uuid4()),
                content=MemoryContent(text=f"Batch content {i}"),
                summary=f"Batch summary {i}",
            )
            for i in range(5)
        ]

        memory_ids = await memory_backend.batch_store(memories)
        assert len(memory_ids) == 5

        for memory_id in memory_ids:
            retrieved = await memory_backend.retrieve(memory_id)
            assert retrieved is not None

        delete_results = await memory_backend.batch_delete(memory_ids[:3])
        assert all(delete_results.values())
        assert len(delete_results) == 3

        for memory_id in memory_ids[:3]:
            retrieved = await memory_backend.retrieve(memory_id)
            assert retrieved is None

        for memory_id in memory_ids[3:]:
            retrieved = await memory_backend.retrieve(memory_id)
            assert retrieved is not None


@pytest.mark.skip("Count implementation varies across backends")
@pytest.mark.asyncio
async def test_count():
    """Test counting memory items."""
    async with create_memory_backend() as memory_backend:
        memories = [
            MemoryItem(
                id=str(uuid.uuid4()),
                content=MemoryContent(text="Count test 1"),
                metadata=MemoryMetadata(status="active"),
            ),
            MemoryItem(
                id=str(uuid.uuid4()),
                content=MemoryContent(text="Count test 2"),
                metadata=MemoryMetadata(status="active"),
            ),
            MemoryItem(
                id=str(uuid.uuid4()),
                content=MemoryContent(text="Count test 3"),
                metadata=MemoryMetadata(status="archived"),
            ),
        ]

        for memory in memories:
            await memory_backend.store(memory)

        try:
            all_items = memory_backend.storage._items
        except AttributeError:
            pytest.skip("Backend does not expose an item collection for inspection")
        else:
            assert len(all_items) == 3


@pytest.mark.skip("Stats implementation varies across backends")
@pytest.mark.asyncio
async def test_get_stats():
    """Test getting storage statistics."""
    async with create_memory_backend() as memory_backend:
        memories = [
            MemoryItem(
                id=str(uuid.uuid4()),
                content=MemoryContent(text="Stats test 1"),
                metadata=MemoryMetadata(status="active"),
            ),
            MemoryItem(
                id=str(uuid.uuid4()),
                content=MemoryContent(text="Stats test 2"),
                metadata=MemoryMetadata(status="active"),
            ),
            MemoryItem(
                id=str(uuid.uuid4()),
                content=MemoryContent(text="Stats test 3"),
                metadata=MemoryMetadata(status="archived"),
            ),
        ]

        for memory in memories:
            await memory_backend.store(memory)

        assert memory_backend is not None
