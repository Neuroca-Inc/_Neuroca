"""Unit tests for working memory helpers used by the memory manager."""

import asyncio
from heapq import heappush
from typing import List

import pytest

from neuroca.memory.backends import MemoryTier
from neuroca.memory.manager.models import RankedMemory
from neuroca.memory.manager.working_memory import (
    get_prompt_context_memories,
    update_working_memory,
)


@pytest.mark.asyncio
async def test_update_working_memory_inserts_unique_ranked_memories():
    """Search results should populate the heap with unseen records."""
    working_memory: List[RankedMemory] = []
    working_memory_ids = {"existing"}

    # Seed heap with a less relevant item to exercise replacement logic.
    heappush(
        working_memory,
        RankedMemory(
            relevance_score=0.1,
            memory_id="existing",
            memory_tier=MemoryTier.STM,
            memory_data={"id": "existing", "tier": MemoryTier.STM.value, "content": {"text": "old"}},
        ),
    )

    async def search_stub(**_: object):  # type: ignore[override]
        return [
            {"id": "mtm-1", "tier": MemoryTier.MTM, "relevance": 0.8},
            {"id": "stm-keep", "tier": MemoryTier.STM, "relevance": 0.4},
            {"id": "existing", "tier": MemoryTier.STM, "relevance": 0.9},
        ]

    lock = asyncio.Lock()
    await update_working_memory(
        current_context={"input": "solve issue", "goal": "ship"},
        context_embeddings=[0.1, 0.2],
        working_memory=working_memory,
        working_memory_ids=working_memory_ids,
        working_buffer_size=2,
        search_memories_func=search_stub,
        lock=lock,
    )

    assert working_memory_ids == {"mtm-1", "stm-keep"}
    assert {item.memory_id for item in working_memory} == {"mtm-1", "stm-keep"}


@pytest.mark.asyncio
async def test_update_working_memory_no_context_returns_early():
    """An empty context should not invoke the search callback."""
    invoked = False

    async def search_stub(**_: object):  # type: ignore[override]
        nonlocal invoked
        invoked = True
        return []

    await update_working_memory(
        current_context={},
        context_embeddings=[],
        working_memory=[],
        working_memory_ids=set(),
        working_buffer_size=1,
        search_memories_func=search_stub,
        lock=asyncio.Lock(),
    )

    assert invoked is False


@pytest.mark.asyncio
async def test_update_working_memory_includes_focus_and_skips_blank_queries():
    """Focus entries should contribute to the query while blank inputs abort the search."""
    observed_queries = []

    async def search_stub(**kwargs):
        observed_queries.append(kwargs["query"])
        return []

    lock = asyncio.Lock()

    await update_working_memory(
        current_context={"input": " ", "focus": "troubleshoot"},
        context_embeddings=[0.0],
        working_memory=[],
        working_memory_ids=set(),
        working_buffer_size=1,
        search_memories_func=search_stub,
        lock=lock,
    )

    await update_working_memory(
        current_context={"input": " ", "goal": "   "},
        context_embeddings=[0.0],
        working_memory=[],
        working_memory_ids=set(),
        working_buffer_size=1,
        search_memories_func=search_stub,
        lock=lock,
    )

    assert observed_queries == ["troubleshoot"]


@pytest.mark.asyncio
async def test_get_prompt_context_memories_orders_and_strengthens_results():
    """Prompt extraction should respect tier formatting and schedule reinforcements."""
    working_memory: List[RankedMemory] = []
    for score, mem_id, tier, content, summary in [
        (0.9, "ltm-1", MemoryTier.LTM, {"content": {"text": "long term"}}, "condensed"),
        (0.7, "mtm-1", MemoryTier.MTM, {"content": {"text": "mid term"}}, "mid summary"),
        (0.5, "stm-1", MemoryTier.STM, {"content": {"text": "short term text"}}, ""),
    ]:
        heappush(
            working_memory,
            RankedMemory(
                relevance_score=score,
                memory_id=mem_id,
                memory_tier=tier,
                memory_data=content,
                summary=summary,
                tags=["tag"],
            ),
        )

    calls = []

    async def strengthen_stub(memory_id, memory_tier, delta):
        calls.append((memory_id, memory_tier, delta))

    lock = asyncio.Lock()
    results = await get_prompt_context_memories(
        working_memory=working_memory,
        working_memory_ids={"ltm-1", "mtm-1", "stm-1"},
        max_memories=2,
        max_tokens_per_memory=2,
        strengthen_memory_func=strengthen_stub,
        lock=lock,
    )

    await asyncio.sleep(0)

    # The heap is a min-heap on relevance_score, so the lowest scores surface first.
    assert [memory["id"] for memory in results] == ["stm-1", "mtm-1"]
    assert all(len(memory["content"].split()) <= 3 for memory in results)
    assert any(call[0] == "stm-1" for call in calls)
    assert any(call[0] == "mtm-1" for call in calls)


@pytest.mark.asyncio
async def test_get_prompt_context_memories_without_lock_covers_all_branches():
    """The no-lock path should handle tier-specific formatting and fallbacks."""
    working_memory: List[RankedMemory] = []
    entries = [
        (0.1, "stm-dict", MemoryTier.STM, {"content": {"text": "stm text"}}, ""),
        (0.2, "stm-str", MemoryTier.STM, {"content": "short string"}, ""),
        (0.3, "mtm-dict", MemoryTier.MTM, {"content": {"text": "mid text"}}, ""),
        (0.4, "mtm-str", MemoryTier.MTM, {"content": "raw mid"}, ""),
        (0.5, "ltm-summary", MemoryTier.LTM, {"content": {"text": "long text"}}, "with summary"),
        (0.6, "ltm-dict", MemoryTier.LTM, {"content": {"text": "alt long"}}, ""),
        (0.7, "ltm-no-text", MemoryTier.LTM, {"content": {"summary": "alt"}}, ""),
        (0.8, "unknown-dict", None, {"content": {"text": "fallback"}}, ""),
        (0.9, "unknown-str", None, {"content": "raw"}, ""),
    ]

    for score, mem_id, tier, content, summary in entries:
        heappush(
            working_memory,
            RankedMemory(
                relevance_score=score,
                memory_id=mem_id,
                memory_tier=tier,
                memory_data=content,
                summary=summary,
            ),
        )

    results = await get_prompt_context_memories(
        working_memory=working_memory,
        working_memory_ids={mem_id for _, mem_id, _, _, _ in entries},
        max_memories=len(entries),
        max_tokens_per_memory=1,
        strengthen_memory_func=None,
        lock=None,
    )

    returned_ids = [item["id"] for item in results]
    assert returned_ids == [mem_id for _, mem_id, _, _, _ in entries]
    summary_contents = {item["id"]: item["content"] for item in results}
    assert summary_contents["stm-dict"].startswith("stm")
    assert summary_contents["stm-str"].endswith("...")
    assert summary_contents["mtm-dict"].startswith("mid")
    assert summary_contents["mtm-str"].endswith("...")
    assert summary_contents["ltm-summary"].startswith("with")
    assert summary_contents["ltm-dict"].startswith("alt")
    assert summary_contents["ltm-no-text"].startswith("{'summary'")
    assert summary_contents["unknown-dict"].startswith("fallback")
    assert summary_contents["unknown-str"].startswith("raw")
