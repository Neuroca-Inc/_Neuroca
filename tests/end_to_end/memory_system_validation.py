"""End-to-end validation for the asynchronous memory manager.

This module exercises the production memory manager against the in-memory
backend to verify that tier initialization, storage, retrieval, search, manual
consolidation, and shutdown behaviours all work together. The previous version
of this script predated the asynchronous refactor and no longer interacted with
the manager correctly; it has been rewritten as a focused pytest suite that
keeps execution time short while still covering the critical orchestration
paths.
"""

from __future__ import annotations

from typing import Any, Dict, List

import pytest

from neuroca.memory.backends.factory import BackendType
from neuroca.memory.manager.memory_manager import MemoryManager


def _build_sample_payloads() -> List[Dict[str, Any]]:
    """Return deterministic memory payloads spanning multiple categories."""

    return [
        {
            "content": "General memory 0: milestone planning for the release.",
            "summary": "General milestone note",
            "importance": 0.3,
            "category": "general",
            "tags": ["general", "validation"],
        },
        {
            "content": "Science memory 1: latest discussion about particle physics.",
            "summary": "Science update",
            "importance": 0.7,
            "category": "science",
            "tags": ["science", "physics"],
        },
        {
            "content": "History memory 2: lessons learned from legacy deployments.",
            "summary": "History insight",
            "importance": 0.5,
            "category": "history",
            "tags": ["history", "archive"],
        },
        {
            "content": "Engineering memory 3: evaluating knowledge graph adapters.",
            "summary": "Engineering evaluation",
            "importance": 0.6,
            "category": "engineering",
            "tags": ["engineering", "graph"],
        },
        {
            "content": "Operations memory 4: observability metrics roll-out plan.",
            "summary": "Operations metrics",
            "importance": 0.4,
            "category": "operations",
            "tags": ["operations", "metrics"],
        },
    ]


@pytest.mark.asyncio
async def test_memory_system_end_to_end() -> None:
    """Exercise storage, retrieval, search, and consolidation across tiers."""

    manager = MemoryManager(backend_type=BackendType.MEMORY)
    try:
        await manager.initialize()

        payloads = _build_sample_payloads()
        memory_ids: List[str] = []

        for payload in payloads:
            memory_id = await manager.add_memory(
                content=payload["content"],
                summary=payload["summary"],
                importance=payload["importance"],
                metadata={"category": payload["category"]},
                tags=payload["tags"],
            )
            assert isinstance(memory_id, str), "add_memory must return a string identifier"
            memory_ids.append(memory_id)

        stm_count = await manager.stm_storage.count()
        assert stm_count == len(payloads), "STM tier should contain all freshly stored memories"

        retrieved_item = await manager.retrieve_memory(memory_ids[0])
        assert retrieved_item is not None, "Stored memory must be retrievable by identifier"
        assert payloads[0]["content"] in retrieved_item.content.primary_text

        search_results = await manager.search_memories(query="physics", limit=5)
        assert any(
            "physics" in result.get("content", {}).get("text", "")
            for result in search_results
        ), "Text search should surface the science payload"

        tag_results = await manager.search_memories(tags=["engineering"], limit=5)
        assert tag_results, "Tag-based filtering should match the engineering payload"

        await manager.update_context({"text": "Discussing cross-tier consolidation"})
        prompt_context = await manager.get_prompt_context_memories(max_memories=3)
        assert prompt_context, "Prompt context extraction should yield relevant memories"

        consolidated_id = await manager.consolidate_memory(
            memory_ids[0], manager.STM_TIER, manager.MTM_TIER
        )
        assert isinstance(consolidated_id, str)

        mtm_item = await manager.mtm_storage.retrieve(consolidated_id)
        assert mtm_item is not None, "Consolidated memory must exist in MTM"

        stm_post_item = await manager.stm_storage.retrieve(memory_ids[0])
        assert stm_post_item is None, "Source tier should not retain the consolidated memory"


    finally:
        await manager.shutdown()
