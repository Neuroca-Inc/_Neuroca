"""Operation helpers for the memory soak-test harness."""

from __future__ import annotations

import asyncio
import random
from collections import Counter
from typing import Any, List, MutableMapping, Optional

from neuroca.memory.manager.memory_manager import MemoryManager


def _random_sentence(rng: random.Random, *, word_count: int = 12) -> str:
    """Create a deterministic pseudo-random sentence for memory payloads.

    Args:
        rng: Seeded pseudo-random generator shared across the harness.
        word_count: Number of words to include in the generated sentence.

    Returns:
        Deterministic sentence composed of lowercase ASCII tokens.

    Raises:
        ValueError: If ``word_count`` is not a positive integer.
    """

    if word_count <= 0:
        raise ValueError("word_count must be positive")

    alphabet = "abcdefghijklmnopqrstuvwxyz"
    return " ".join(
        "".join(rng.choice(alphabet) for _ in range(rng.randint(4, 10)))
        for _ in range(word_count)
    )


def _update_backlog(last_access: MutableMapping[str, float], memory_id: str) -> None:
    """Record the latest access timestamp for ``memory_id``.

    Args:
        last_access: Mapping tracking the most recent interaction per memory.
        memory_id: Identifier of the memory that was just touched.

    Side Effects:
        Mutates ``last_access`` in place.
    """

    import time

    last_access[str(memory_id)] = time.perf_counter()


async def _store_memory(
    manager: MemoryManager,
    *,
    state: MutableMapping[str, Any],
    sentence: str,
    topic: str,
) -> Optional[str]:
    """Persist a new memory item and update state trackers.

    Args:
        manager: Active memory manager instance.
        state: Mutable soak-test state containing counters and buffers.
        sentence: Text content to store in the memory item.
        topic: Topic tag associated with the generated memory.

    Returns:
        Identifier of the stored memory when successful; ``None`` otherwise.

    Side Effects:
        Mutates ``state`` to reflect the newly created memory.
    """

    try:
        memory_id = await manager.add_memory(
            content=sentence,
            summary=f"soak-memory-{state['operations']}",
            importance=0.45,
            metadata={"topic": topic, "source": "soak"},
            tags=[topic],
        )
    except Exception as exc:  # noqa: BLE001
        state["errors"].append(f"add_memory failed: {exc}")
        return None

    identifier = str(memory_id)
    state["operations"] += 1
    state["all_ids"].add(identifier)
    state["stm_ids"].append(identifier)
    _update_backlog(state["last_access"], identifier)
    return identifier


async def _promote_if_ready(
    manager: MemoryManager,
    *,
    source_tier: str,
    target_tier: str,
    source_ids: List[str],
    target_ids: List[str],
    state: MutableMapping[str, Any],
    promotions: Counter,
) -> None:
    """Promote the oldest entry from ``source_ids`` when available.

    Args:
        manager: Active memory manager instance.
        source_tier: Canonical tier name being promoted from.
        target_tier: Canonical tier name receiving the memory.
        source_ids: FIFO list of identifiers held in the source tier.
        target_ids: FIFO list representing the destination tier.
        state: Mutable soak-test state tracking counters and identifier sets.
        promotions: Counter updated with successful promotion counts.

    Side Effects:
        Mutates ``state`` and the tier identifier lists when promotions occur.
    """

    if not source_ids:
        return

    candidate = source_ids.pop(0)
    state["operations"] += 1

    try:
        new_identifier = await manager.consolidate_memory(
            memory_id=candidate,
            source_tier=source_tier,
            target_tier=target_tier,
            additional_metadata={"promoted_by": "soak"},
        )
    except Exception as exc:  # noqa: BLE001
        state["errors"].append(f"consolidation {source_tier}->{target_tier} failed: {exc}")
        return

    if new_identifier is None:
        return

    identifier = str(new_identifier)
    state["all_ids"].discard(str(candidate))
    state["all_ids"].add(identifier)
    target_ids.append(identifier)
    promotions[(source_tier, target_tier)] += 1
    _update_backlog(state["last_access"], identifier)


async def _maybe_promote_tiers(
    manager: MemoryManager,
    *,
    state: MutableMapping[str, Any],
    promotions: Counter,
) -> None:
    """Trigger promotions based on the operation counter thresholds.

    Args:
        manager: Active memory manager instance.
        state: Mutable soak-test state containing identifier buffers.
        promotions: Counter recording promotion totals per transition.
    """

    if state["operations"] % 3 == 0:
        await _promote_if_ready(
            manager,
            source_tier=manager.STM_TIER,
            target_tier=manager.MTM_TIER,
            source_ids=state["stm_ids"],
            target_ids=state["mtm_ids"],
            state=state,
            promotions=promotions,
        )

    if state["operations"] % 5 == 0:
        await _promote_if_ready(
            manager,
            source_tier=manager.MTM_TIER,
            target_tier=manager.LTM_TIER,
            source_ids=state["mtm_ids"],
            target_ids=state["ltm_ids"],
            state=state,
            promotions=promotions,
        )


async def _apply_decay(
    manager: MemoryManager,
    *,
    rng: random.Random,
    state: MutableMapping[str, Any],
    decay_counts: Counter,
) -> None:
    """Randomly decay a stored memory across the available tiers.

    Args:
        manager: Active memory manager instance.
        rng: Random number generator controlling tier selection.
        state: Mutable soak-test state tracking identifier buffers.
        decay_counts: Counter recording per-tier decay attempts.
    """

    tier_names = [manager.STM_TIER, manager.MTM_TIER, manager.LTM_TIER]
    pools = [state["stm_ids"], state["mtm_ids"], state["ltm_ids"]]
    populated = [(tier, pool) for tier, pool in zip(tier_names, pools) if pool]
    if not populated:
        return

    tier, pool = rng.choice(populated)
    target = rng.choice(pool)
    state["operations"] += 1
    try:
        await manager.decay_memory(target, tier=tier, decay_amount=0.05)
    except Exception as exc:  # noqa: BLE001
        state["errors"].append(f"decay {tier} failed for {target}: {exc}")
        return

    decay_counts[tier] += 1
    _update_backlog(state["last_access"], target)


async def _maybe_decay_and_retrieve(
    manager: MemoryManager,
    *,
    rng: random.Random,
    state: MutableMapping[str, Any],
    decay_counts: Counter,
) -> None:
    """Apply decay and retrieve a random memory when thresholds match.

    Args:
        manager: Active memory manager instance.
        rng: Deterministic random number generator for selection.
        state: Mutable soak-test state tracking identifiers.
        decay_counts: Counter recording per-tier decay attempts.
    """

    if state["operations"] % 4 == 0:
        await _apply_decay(manager, rng=rng, state=state, decay_counts=decay_counts)

    if state["operations"] % 2 != 0:
        return

    target_pool: List[str] = []
    target_pool.extend(state["stm_ids"])
    target_pool.extend(state["mtm_ids"])
    target_pool.extend(state["ltm_ids"])
    if not target_pool:
        return

    chosen = rng.choice(target_pool)
    try:
        await manager.retrieve_memory(chosen)
    except Exception as exc:  # noqa: BLE001
        state["errors"].append(f"retrieve_memory failed for {chosen}: {exc}")
    else:
        _update_backlog(state["last_access"], chosen)
    finally:
        state["operations"] += 1


async def _execute_operation_batch(
    manager: MemoryManager,
    *,
    rng: random.Random,
    batch_size: int,
    state: MutableMapping[str, Any],
    promotions: Counter,
    decay_counts: Counter,
) -> None:
    """Execute a batch of CRUD, consolidation, and decay operations.

    Args:
        manager: Active memory manager under test.
        rng: Random number generator ensuring deterministic payloads.
        batch_size: Number of new memories to create in the batch.
        state: Mutable soak-test state tracking identifiers and metrics.
        promotions: Counter recording promotion totals per tier transition.
        decay_counts: Counter recording decay attempts per tier.

    Side Effects:
        Mutates ``state`` and the promotion/decay counters.
    """

    for index in range(batch_size):
        sentence = _random_sentence(rng)
        topic = f"soak-{index % 5}"
        identifier = await _store_memory(
            manager,
            state=state,
            sentence=sentence,
            topic=topic,
        )
        if identifier is None:
            continue

        await _maybe_promote_tiers(manager, state=state, promotions=promotions)
        await _maybe_decay_and_retrieve(
            manager,
            rng=rng,
            state=state,
            decay_counts=decay_counts,
        )

    await asyncio.sleep(0)


__all__ = [
    "_random_sentence",
    "_update_backlog",
    "_store_memory",
    "_promote_if_ready",
    "_maybe_promote_tiers",
    "_apply_decay",
    "_maybe_decay_and_retrieve",
    "_execute_operation_batch",
]
