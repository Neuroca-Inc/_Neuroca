"""Asynchronous performance sanity checks for the memory system.

This module provides lightweight helpers that execute a minimal batch of
operations against the storage backends, individual memory tiers, and the
memory manager. The goal is not to provide statistically rigorous
benchmarks, but to confirm that the asynchronous APIs remain functional
after recent refactors.
"""

from __future__ import annotations

import asyncio
import random
import statistics
import time
from typing import Callable, Dict, Mapping, MutableMapping, Sequence, Tuple

from neuroca.memory.backends.factory.backend_type import BackendType
from neuroca.memory.backends.factory.memory_tier import MemoryTier as BackendMemoryTier
from neuroca.memory.backends.factory.storage_factory import StorageBackendFactory
from neuroca.memory.interfaces.storage_backend import StorageBackendInterface
from neuroca.memory.manager.memory_manager import MemoryManager
from neuroca.memory.models.memory_item import MemoryContent, MemoryItem, MemoryMetadata
from neuroca.memory.tiers.base import BaseMemoryTier
from neuroca.memory.tiers.ltm.core import LongTermMemory
from neuroca.memory.tiers.mtm.core import MediumTermMemory
from neuroca.memory.tiers.stm.core import ShortTermMemory


def _random_sentence(rng: random.Random, word_count: int = 12) -> str:
    """Generate a deterministic pseudo-random sentence for benchmark data.

    Args:
        rng: Shared random number generator seeded by the caller.
        word_count: Number of words to include in the generated sentence.

    Returns:
        A whitespace separated sentence containing ASCII words.
    """

    alphabet = "abcdefghijklmnopqrstuvwxyz"
    words = []
    for _ in range(word_count):
        letters = [rng.choice(alphabet) for _ in range(rng.randint(4, 10))]
        words.append("".join(letters))
    return " ".join(words)


def _build_memory_item(index: int, rng: random.Random) -> MemoryItem:
    """Create a MemoryItem with synthetic content and metadata.

    Args:
        index: Sequential index used to ensure deterministic identifiers.
        rng: Shared pseudo-random number generator.

    Returns:
        A populated MemoryItem instance ready for storage.
    """

    content = MemoryContent(text=_random_sentence(rng))
    metadata = MemoryMetadata(
        importance=min(1.0, 0.2 + (index % 10) * 0.07),
        tags={"topic": f"synthetic-{index % 5}"},
        source="benchmark",
    )
    return MemoryItem(content=content, metadata=metadata, summary=f"item-{index}")


def build_sample_items(count: int, seed: int = 42) -> Sequence[MemoryItem]:
    """Create a deterministic collection of MemoryItem objects.

    Args:
        count: Number of MemoryItem instances to create.
        seed: Random seed for reproducible content generation.

    Returns:
        Sequence of MemoryItem objects with predictable content.
    """

    rng = random.Random(seed)
    return [_build_memory_item(index, rng) for index in range(count)]


def _percentile(samples: Sequence[float], percentile: float) -> float:
    """Compute a percentile value from the provided samples.

    Args:
        samples: Iterable collection of numeric samples.
        percentile: Target percentile expressed as a value between 0 and 100.

    Returns:
        The percentile value or ``0.0`` when the input is empty.
    """

    if not samples:
        return 0.0

    ordered = sorted(samples)
    rank = (percentile / 100.0) * (len(ordered) - 1)
    lower_index = int(rank)
    upper_index = min(lower_index + 1, len(ordered) - 1)
    weight = rank - lower_index
    return (1 - weight) * ordered[lower_index] + weight * ordered[upper_index]


def summarize_samples(samples: Sequence[float]) -> Dict[str, float]:
    """Build descriptive statistics for a collection of samples.

    Args:
        samples: Recorded durations in seconds.

    Returns:
        Mapping that contains ``count``, ``mean``, ``median``, ``stdev``, and ``p95``.
    """

    if not samples:
        return {"count": 0.0, "mean": 0.0, "median": 0.0, "stdev": 0.0, "p95": 0.0}

    return {
        "count": float(len(samples)),
        "mean": statistics.fmean(samples),
        "median": statistics.median(samples),
        "stdev": statistics.pstdev(samples),
        "p95": _percentile(samples, 95.0),
    }


async def _time_create(
    backend: StorageBackendInterface,
    items: Sequence[MemoryItem],
) -> Tuple[Sequence[str], Sequence[float]]:
    """Measure ``create`` latency for the provided items.

    Args:
        backend: Initialized storage backend instance.
        items: Collection of MemoryItem objects to persist.

    Returns:
        Tuple containing generated identifiers and associated durations.
    """

    durations = []
    identifiers = []
    for item in items:
        start = time.perf_counter()
        await backend.create(item.id, item.model_dump(mode="json"))
        durations.append(time.perf_counter() - start)
        identifiers.append(item.id)
    return identifiers, durations


async def _time_read(
    backend: StorageBackendInterface,
    identifiers: Sequence[str],
) -> Sequence[float]:
    """Measure ``read`` latency for the provided identifiers."""

    durations = []
    for memory_id in identifiers:
        start = time.perf_counter()
        await backend.read(memory_id)
        durations.append(time.perf_counter() - start)
    return durations


async def _time_update(
    backend: StorageBackendInterface,
    items: Sequence[MemoryItem],
    identifiers: Sequence[str],
) -> Sequence[float]:
    """Measure ``update`` latency for the provided items."""

    durations = []
    for item, memory_id in zip(items, identifiers):
        updated = item.model_copy(deep=True)
        updated.metadata.strength = min(1.0, updated.metadata.strength + 0.1)
        updated.summary = f"{item.summary}-updated"
        start = time.perf_counter()
        await backend.update(memory_id, updated.model_dump(mode="json"))
        durations.append(time.perf_counter() - start)
    return durations


async def _time_delete(
    backend: StorageBackendInterface,
    identifiers: Sequence[str],
) -> Sequence[float]:
    """Measure ``delete`` latency for the provided identifiers."""

    durations = []
    for memory_id in identifiers:
        start = time.perf_counter()
        await backend.delete(memory_id)
        durations.append(time.perf_counter() - start)
    return durations


async def benchmark_backend_operations(
    backend_type: BackendType,
    items: Sequence[MemoryItem],
) -> Mapping[str, Dict[str, float]]:
    """Execute CRUD operations against a storage backend instance.

    Args:
        backend_type: The backend implementation to exercise.
        items: Memories that should be written to the backend.

    Returns:
        Mapping of operation name to timing summaries.
    """

    backend = StorageBackendFactory.create_storage(
        tier=BackendMemoryTier.STM,
        backend_type=backend_type,
        config={},
        use_existing=False,
    )
    await backend.initialize()
    try:
        identifiers, create_samples = await _time_create(backend, items)
        read_samples = await _time_read(backend, identifiers)
        update_samples = await _time_update(backend, items, identifiers)
        delete_samples = await _time_delete(backend, identifiers)
        return {
            "create": summarize_samples(create_samples),
            "read": summarize_samples(read_samples),
            "update": summarize_samples(update_samples),
            "delete": summarize_samples(delete_samples),
        }
    finally:
        await backend.clear()
        await backend.shutdown()


async def _benchmark_tier(
    tier_factory: Callable[[], BaseMemoryTier],
    items: Sequence[MemoryItem],
) -> Mapping[str, Dict[str, float]]:
    """Run store/retrieve/delete operations on a specific memory tier."""

    tier = tier_factory()
    await tier.initialize()
    try:
        store_durations = []
        identifiers = []
        for item in items:
            start = time.perf_counter()
            memory_id = await tier.store(item)
            store_durations.append(time.perf_counter() - start)
            identifiers.append(memory_id)

        retrieve_durations = []
        for memory_id in identifiers:
            start = time.perf_counter()
            await tier.retrieve(memory_id)
            retrieve_durations.append(time.perf_counter() - start)

        delete_durations = []
        for memory_id in identifiers:
            start = time.perf_counter()
            await tier.delete(memory_id)
            delete_durations.append(time.perf_counter() - start)

        return {
            "store": summarize_samples(store_durations),
            "retrieve": summarize_samples(retrieve_durations),
            "delete": summarize_samples(delete_durations),
        }
    finally:
        await tier.shutdown()


async def benchmark_tiers(items: Sequence[MemoryItem]) -> Mapping[str, Mapping[str, Dict[str, float]]]:
    """Benchmark STM, MTM, and LTM tiers sequentially."""

    tiers = {
        "stm": lambda: ShortTermMemory(backend_type=BackendType.MEMORY),
        "mtm": lambda: MediumTermMemory(backend_type=BackendType.MEMORY),
        "ltm": lambda: LongTermMemory(backend_type=BackendType.MEMORY),
    }
    results: MutableMapping[str, Mapping[str, Dict[str, float]]] = {}
    for name, tier_factory in tiers.items():
        results[name] = await _benchmark_tier(tier_factory, items)
    return results


async def benchmark_memory_manager(items: Sequence[MemoryItem]) -> Mapping[str, Dict[str, float]]:
    """Exercise the MemoryManager asynchronous API surface."""

    manager = MemoryManager(backend_type=BackendType.MEMORY)
    await manager.initialize()
    try:
        add_samples = []
        identifiers = []
        for item in items:
            metadata_payload = item.metadata.model_dump(mode="json")
            metadata_payload.pop("importance", None)
            start = time.perf_counter()
            memory_id = await manager.add_memory(
                content=item.get_text(),
                summary=item.summary,
                importance=item.metadata.importance,
                metadata=metadata_payload,
                tags=list(item.metadata.tags.keys()),
            )
            add_samples.append(time.perf_counter() - start)
            identifiers.append(memory_id)

        retrieve_samples = []
        for memory_id in identifiers:
            start = time.perf_counter()
            await manager.retrieve_memory(memory_id)
            retrieve_samples.append(time.perf_counter() - start)

        search_samples = []
        for item in items[: min(5, len(items))]:
            start = time.perf_counter()
            await manager.search_memories(query=item.get_text(), limit=3)
            search_samples.append(time.perf_counter() - start)

        delete_samples = []
        for memory_id in identifiers:
            start = time.perf_counter()
            await manager.delete_memory(memory_id)
            delete_samples.append(time.perf_counter() - start)

        return {
            "add_memory": summarize_samples(add_samples),
            "retrieve_memory": summarize_samples(retrieve_samples),
            "search_memories": summarize_samples(search_samples),
            "delete_memory": summarize_samples(delete_samples),
        }
    finally:
        await manager.shutdown()


def _format_summary(operation: str, stats: Mapping[str, float]) -> str:
    """Format a single operation summary for console output."""

    count = int(stats.get("count", 0.0))
    mean_ms = stats.get("mean", 0.0) * 1000.0
    p95_ms = stats.get("p95", 0.0) * 1000.0
    return f"  {operation:<16}count={count:>3} mean={mean_ms:>7.3f}ms p95={p95_ms:>7.3f}ms"


def print_results(section: str, results: Mapping[str, Mapping[str, float]]) -> None:
    """Print formatted benchmark results for a section."""

    print(f"\n{section}")
    for operation, stats in results.items():
        print(_format_summary(operation, stats))


async def main() -> None:
    """Run the asynchronous benchmark sampler and print summaries."""

    sample_items = build_sample_items(count=32)

    backend_results = await benchmark_backend_operations(BackendType.MEMORY, sample_items)
    print_results("Storage Backend (In-Memory)", backend_results)

    tier_results = await benchmark_tiers(sample_items)
    for tier_name, operations in tier_results.items():
        print_results(f"Tier: {tier_name.upper()}", operations)

    manager_results = await benchmark_memory_manager(sample_items)
    print_results("Memory Manager", manager_results)


if __name__ == "__main__":
    asyncio.run(main())
