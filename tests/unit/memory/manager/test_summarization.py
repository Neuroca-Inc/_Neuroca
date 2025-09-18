from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta
import re
from typing import Any, Dict, List, Set

import pytest

from neuroca.memory.manager.consolidation import consolidate_mtm_to_ltm
from neuroca.memory.manager.summarization import (
    DEFAULT_STOP_WORDS,
    MemorySummarizer,
    SummarizationPayload,
)


def test_keyword_backend_generates_weighted_batch_summary() -> None:
    summarizer = MemorySummarizer.from_config({})

    payloads = [
        SummarizationPayload(
            memory_id="critical",
            text="Critical failure on node alpha. Database went offline abruptly.",
            importance=0.95,
            tags=["incident", "database"],
        ),
        SummarizationPayload(
            memory_id="routine",
            text="Routine health report shows stable operations and successful backups.",
            importance=0.2,
            tags=["report"],
        ),
    ]

    result = summarizer.summarize_payloads(payloads)

    assert "Critical failure on node alpha." in result.aggregated_summary
    assert "incident" in result.keywords
    assert result.per_item["critical"].startswith("Critical failure")
    assert result.highlights["critical"]


def test_summarizer_respects_custom_sentence_and_keyword_limits() -> None:
    summarizer = MemorySummarizer.from_config(
        {
            "options": {
                "max_batch_summary_sentences": 1,
                "max_item_summary_sentences": 1,
                "max_keywords": 2,
            }
        }
    )

    payload = SummarizationPayload(
        memory_id="m1",
        text=(
            "First sentence details the outage impact. "
            "Second sentence elaborates on mitigation steps. "
            "Third sentence covers preventative measures."
        ),
        importance=0.85,
    )

    result = summarizer.summarize_payloads([payload])

    assert len(result.highlights["m1"]) == 1
    assert len(result.keywords) <= 2


def _token_set(text: str) -> Set[str]:
    return {
        token
        for token in re.findall(r"\b[\w']+\b", text.lower())
        if token and token not in DEFAULT_STOP_WORDS
    }


def test_batch_summary_retains_salient_entities() -> None:
    summarizer = MemorySummarizer.from_config({})

    payloads = [
        SummarizationPayload(
            memory_id="critical",
            text=(
                "Team Aurora isolated cascading failure impacting Redwood clients. "
                "Immediate failover protected Hydra workloads from broader impact."
            ),
            importance=0.92,
            tags=["incident", "aurora"],
        ),
        SummarizationPayload(
            memory_id="analysis",
            text=(
                "Phoenix audit logs confirmed gateway throttling recovered after temporary scaling. "
                "Runbooks highlighted new containment policies."
            ),
            importance=0.68,
            tags=["phoenix"],
        ),
        SummarizationPayload(
            memory_id="routine",
            text="Daily status report recorded no lingering alerts or customer escalations.",
            importance=0.15,
            tags=["status"],
        ),
    ]

    result = summarizer.summarize_payloads(payloads)

    capitalised_tokens = set(re.findall(r"\b[A-Z][A-Za-z0-9_-]+\b", result.aggregated_summary))
    assert {"Aurora", "Redwood", "Hydra"}.issubset(capitalised_tokens)

    keyword_tokens = set(result.keywords)
    assert "aurora" in keyword_tokens

    highlights = result.highlights["critical"]
    assert any("Aurora" in sentence for sentence in highlights)


def test_batch_summary_preserves_semantic_overlap() -> None:
    summarizer = MemorySummarizer.from_config(
        {
            "options": {
                "max_batch_summary_sentences": 3,
                "max_item_summary_sentences": 2,
                "max_keywords": 8,
            }
        }
    )

    payloads = [
        SummarizationPayload(
            memory_id="aurora",
            text=(
                "Aurora pipeline triggered redundant failover for Redwood clients after telemetry spikes. "
                "Engineers documented mitigations and staged a gradual rollout to prevent regression."
            ),
            importance=0.94,
            tags=["aurora", "failover"],
        ),
        SummarizationPayload(
            memory_id="hydra",
            text=(
                "Hydra cache layer absorbed spillover traffic but reported elevated tail latency. "
                "Coordinated tuning reduced saturation while keeping session integrity intact."
            ),
            importance=0.71,
            tags=["hydra", "latency"],
        ),
        SummarizationPayload(
            memory_id="routine",
            text="Daily rotation checklist completed without additional intervention.",
            importance=0.18,
        ),
    ]

    result = summarizer.summarize_payloads(payloads)

    summary_tokens = _token_set(result.aggregated_summary)
    assert summary_tokens

    weighted_source: Counter[str] = Counter()
    for payload in payloads:
        for token in _token_set(payload.text):
            weighted_source[token] += payload.importance_weight()

    top_tokens = {token for token, _ in weighted_source.most_common(max(len(summary_tokens), 6))}
    overlap = len(summary_tokens & top_tokens) / max(1, len(top_tokens))

    assert overlap >= 0.6


@dataclass
class FakeMTMMemory:
    id: str
    content: Dict[str, Any]
    metadata: Dict[str, Any]
    tags: List[str]
    created_at: datetime
    access_count: int


class FakeMTMStorage:
    def __init__(self, memories: List[FakeMTMMemory]):
        self._memories = memories
        self.consolidated: List[str] = []

    async def search(self, min_priority: Any = None) -> List[FakeMTMMemory]:  # noqa: ANN401
        return self._memories

    async def consolidate_memory(self, memory_id: str) -> None:
        self.consolidated.append(memory_id)


class FakeLTMStorage:
    def __init__(self) -> None:
        self.stored: List[Any] = []

    async def store(self, item: Any) -> str:  # noqa: ANN401
        self.stored.append(item)
        return f"ltm-{len(self.stored)}"


@pytest.mark.asyncio
async def test_consolidation_uses_advanced_summarizer_metadata() -> None:
    base_created = datetime.now() - timedelta(days=45)
    mtm_memories = [
        FakeMTMMemory(
            id="mtm-1",
            content={
                "text": "Critical outage resolved after coordinated restart. Customers impacted across region.",
            },
            metadata={
                "importance": 0.92,
                "additional_metadata": {"origin": "ops_journal"},
            },
            tags=["incident", "sev1"],
            created_at=base_created,
            access_count=20,
        ),
        FakeMTMMemory(
            id="mtm-2",
            content={
                "text": "Postmortem analysis isolated root cause to configuration drift and missing guardrails.",
            },
            metadata={
                "importance": 0.82,
                "additional_metadata": {"origin": "ops_journal"},
            },
            tags=["analysis"],
            created_at=base_created,
            access_count=18,
        ),
    ]

    mtm_storage = FakeMTMStorage(mtm_memories)
    ltm_storage = FakeLTMStorage()

    config = {
        "consolidation_batch_size": 5,
        "summarization": {
            "options": {
                "max_batch_summary_sentences": 2,
                "max_item_summary_sentences": 2,
            }
        },
    }

    await consolidate_mtm_to_ltm(mtm_storage, ltm_storage, config)

    assert mtm_storage.consolidated == ["mtm-1", "mtm-2"]
    assert len(ltm_storage.stored) == 2

    summaries = [item.summary for item in ltm_storage.stored]
    assert any("Critical outage" in summary for summary in summaries)

    summarization_meta = ltm_storage.stored[0].metadata.additional_metadata["summarization"]
    assert summarization_meta["aggregated"]
    assert summarization_meta["keywords"]
    assert summarization_meta["highlights"]
