"""Integration tests exercising the modern tiered memory workflow."""

from __future__ import annotations

from typing import Dict, List

import pytest
import pytest_asyncio

from neuroca.memory.factory import create_test_memory_manager
from neuroca.memory.manager import MemoryManager


@pytest_asyncio.fixture()
async def memory_manager() -> MemoryManager:
    """Provision an initialized memory manager backed by in-memory tiers."""

    manager = create_test_memory_manager()
    await manager.initialize()
    try:
        yield manager
    finally:
        await manager.shutdown()


@pytest.fixture()
def sample_payloads() -> List[Dict[str, object]]:
    """Return canonical payloads used to exercise tier hand-offs."""

    return [
        {
            "content": "Short-term insight about integration",
            "summary": "STM insight",
            "importance": 0.85,
            "metadata": {"source": "integration-test", "topic": "stm"},
            "tags": ["integration", "stm"],
        },
        {
            "content": "Medium-term memory retained for planning",
            "summary": "MTM planning snippet",
            "importance": 0.65,
            "metadata": {"source": "integration-test", "topic": "mtm"},
            "tags": ["integration", "mtm"],
        },
        {
            "content": "Long-term knowledge ready for consolidation",
            "summary": "LTM consolidation candidate",
            "importance": 0.9,
            "metadata": {"source": "integration-test", "topic": "ltm"},
            "tags": ["integration", "ltm"],
        },
    ]


@pytest.mark.asyncio
async def test_memory_flow_between_tiers(
    memory_manager: MemoryManager, sample_payloads: List[Dict[str, object]]
) -> None:
    """Promote a memory across STM → MTM → LTM and confirm metadata preservation."""

    stm_entry = sample_payloads[0]
    stm_id = await memory_manager.add_memory(
        content=str(stm_entry["content"]),
        summary=str(stm_entry["summary"]),
        importance=float(stm_entry["importance"]),
        metadata=dict(stm_entry["metadata"]),
        tags=list(stm_entry["tags"]),
        initial_tier=MemoryManager.STM_TIER,
    )

    stm_item = await memory_manager.stm_storage.retrieve(stm_id)
    assert stm_item is not None
    assert getattr(stm_item.metadata, "tier", None) == MemoryManager.STM_TIER

    transferred_item = await memory_manager.transfer_memory(stm_id, MemoryManager.MTM_TIER)
    assert transferred_item is not None
    assert getattr(transferred_item.metadata, "tier", None) == MemoryManager.MTM_TIER
    assert await memory_manager.stm_storage.retrieve(stm_id) is None

    mtm_item = await memory_manager.mtm_storage.retrieve(stm_id)
    assert mtm_item is not None
    assert getattr(mtm_item.metadata, "tier", None) == MemoryManager.MTM_TIER

    consolidated_id = await memory_manager.consolidate_memory(
        stm_id,
        MemoryManager.MTM_TIER,
        MemoryManager.LTM_TIER,
        additional_metadata={"tags": {"ltm_ready": True}},
    )
    assert consolidated_id == stm_id

    assert await memory_manager.mtm_storage.retrieve(stm_id) is None
    assert not await memory_manager.mtm_storage.exists(stm_id)
    ltm_item = await memory_manager.ltm_storage.retrieve(stm_id)
    assert ltm_item is not None
    assert await memory_manager.ltm_storage.exists(stm_id)
    assert ltm_item.metadata.tags.get("ltm_ready") is True

    search_results = await memory_manager.search_memories(
        tags=["integration", "ltm_ready"],
        tiers=[MemoryManager.LTM_TIER],
        min_relevance=0.0,
        limit=5,
    )
    assert isinstance(search_results, list)
    if search_results:
        assert all(result.get("tier") == MemoryManager.LTM_TIER for result in search_results)


@pytest.mark.asyncio
async def test_multi_tier_storage_and_search(
    memory_manager: MemoryManager, sample_payloads: List[Dict[str, object]]
) -> None:
    """Store memories directly in each tier and ensure cross-tier search retrieves them."""

    stm_id = await memory_manager.add_memory(
        content=str(sample_payloads[0]["content"]),
        summary=str(sample_payloads[0]["summary"]),
        importance=float(sample_payloads[0]["importance"]),
        metadata=dict(sample_payloads[0]["metadata"]),
        tags=list(sample_payloads[0]["tags"]),
        initial_tier=MemoryManager.STM_TIER,
    )
    mtm_id = await memory_manager.add_memory(
        content=str(sample_payloads[1]["content"]),
        summary=str(sample_payloads[1]["summary"]),
        importance=float(sample_payloads[1]["importance"]),
        metadata=dict(sample_payloads[1]["metadata"]),
        tags=list(sample_payloads[1]["tags"]),
        initial_tier=MemoryManager.MTM_TIER,
    )
    ltm_id = await memory_manager.add_memory(
        content=str(sample_payloads[2]["content"]),
        summary=str(sample_payloads[2]["summary"]),
        importance=float(sample_payloads[2]["importance"]),
        metadata=dict(sample_payloads[2]["metadata"]),
        tags=list(sample_payloads[2]["tags"]),
        initial_tier=MemoryManager.LTM_TIER,
    )

    assert await memory_manager.stm_storage.exists(stm_id)
    assert await memory_manager.mtm_storage.exists(mtm_id)
    assert await memory_manager.ltm_storage.exists(ltm_id)

    results = await memory_manager.search_memories(
        query="memory",
        tiers=[
            MemoryManager.STM_TIER,
            MemoryManager.MTM_TIER,
            MemoryManager.LTM_TIER,
        ],
        limit=10,
    )
    result_ids = {entry["id"] for entry in results}
    assert {stm_id, mtm_id, ltm_id}.issubset(result_ids)

    context_memories = await memory_manager.get_prompt_context_memories(max_memories=2)
    assert len(context_memories) <= 2
    assert all(isinstance(memory, dict) and "tier" in memory for memory in context_memories)
