"""Asynchronous harness for the memory soak-test workflow."""

from __future__ import annotations

import random
import time
from collections import Counter
from typing import Any, List, Sequence

from neuroca.memory.manager.memory_manager import MemoryManager

from .manager import _initial_state, _initialise_manager
from .metrics import _build_report, _calculate_backlog_age, _promotion_metrics
from .models import SoakTestReport
from .operations import _execute_operation_batch
from .snapshots import _snapshot_and_restore


async def _run_workload_loop(
    manager: MemoryManager,
    *,
    rng: random.Random,
    duration_seconds: float,
    batch_size: int,
    state,
    promotions: Counter,
    decay_counts: Counter,
) -> tuple[int, Exception | None]:
    """Drive the soak workload until the duration window expires.

    Args:
        manager: Active memory manager instance.
        rng: Random number generator controlling deterministic operations.
        duration_seconds: Maximum runtime for the workload loop.
        batch_size: Number of memories to create per batch.
        state: Mutable soak-test state capturing counters and identifiers.
        promotions: Counter recording promotion totals per tier transition.
        decay_counts: Counter recording decay attempts per tier.

    Returns:
        Tuple containing the number of completed cycles and any exception raised
        during execution.
    """

    cycles = 0
    loop_error: Exception | None = None
    deadline = time.perf_counter() + duration_seconds
    try:
        while time.perf_counter() < deadline:
            await _execute_operation_batch(
                manager,
                rng=rng,
                batch_size=batch_size,
                state=state,
                promotions=promotions,
                decay_counts=decay_counts,
            )
            cycles += 1
    except Exception as exc:  # noqa: BLE001
        loop_error = exc
    return cycles, loop_error


async def _run_and_finalize(
    manager: MemoryManager,
    *,
    rng: random.Random,
    duration_seconds: float,
    batch_size: int,
    state,
    promotions: Counter,
    decay_counts: Counter,
    audit_events: Sequence[Any],
    event_ids: Sequence[str],
    backup_dir,
) -> SoakTestReport:
    """Drive the workload loop and return the consolidated soak report.

    Args:
        manager: Active memory manager instance.
        rng: Random number generator controlling deterministic operations.
        duration_seconds: Target runtime for the workload loop.
        batch_size: Number of memories to create per batch.
        state: Mutable soak-test state capturing counters and identifiers.
        promotions: Counter recording promotion totals per tier transition.
        decay_counts: Counter recording decay attempts per tier.
        audit_events: Sequence used to capture emitted audit events.
        event_ids: Sequence tracking audit event identifiers.
        backup_dir: Optional directory where the snapshot will be preserved.

    Returns:
        Populated :class:`SoakTestReport` summarising the soak run.
    """

    started_at = time.perf_counter()
    cycles, loop_error = await _run_workload_loop(
        manager,
        rng=rng,
        duration_seconds=duration_seconds,
        batch_size=batch_size,
        state=state,
        promotions=promotions,
        decay_counts=decay_counts,
    )
    actual_duration = max(0.0, time.perf_counter() - started_at)
    backlog_age = _calculate_backlog_age(state["last_access"])
    total_promotions, promotion_rate = _promotion_metrics(promotions, actual_duration)
    duplicate_ids = len(event_ids) - len(set(event_ids))
    snapshot_path, restore_valid = await _snapshot_and_restore(
        manager,
        state["all_ids"],
        backup_dir,
    )
    if loop_error is not None:
        state["errors"].append(str(loop_error))
    await manager.shutdown()
    return _build_report(
        duration_seconds=actual_duration,
        operations=state["operations"],
        cycles=cycles,
        total_promotions=total_promotions,
        promotion_rate=promotion_rate,
        decay_counts=decay_counts,
        backlog_age=backlog_age,
        audit_events=audit_events,
        duplicate_ids=duplicate_ids,
        snapshot_path=snapshot_path,
        restore_valid=restore_valid,
        errors=state["errors"],
    )


async def run_soak_test(
    *,
    duration_seconds: float = 30.0,
    batch_size: int = 12,
    maintenance_interval: float = 0.0,
    seed: int = 1337,
    backup_dir = None,
) -> SoakTestReport:
    """Execute the soak test and return collected metrics.

    Args:
        duration_seconds: Target runtime for the harness in seconds.
        batch_size: Number of new memories to create per iteration batch.
        maintenance_interval: Recorded maintenance interval for parity with
            production configuration.
        seed: Random seed to keep payload generation deterministic.
        backup_dir: Optional directory where the snapshot will be preserved.

    Returns:
        Populated :class:`SoakTestReport` describing the captured metrics.
    """

    audit_events: List[Any] = []
    event_ids: List[str] = []
    manager: MemoryManager = await _initialise_manager(
        maintenance_interval,
        audit_events=audit_events,
        event_ids=event_ids,
    )
    rng = random.Random(seed)
    state = _initial_state()
    promotions: Counter = Counter()
    decay_counts: Counter = Counter()
    return await _run_and_finalize(
        manager,
        rng=rng,
        duration_seconds=duration_seconds,
        batch_size=batch_size,
        state=state,
        promotions=promotions,
        decay_counts=decay_counts,
        audit_events=audit_events,
        event_ids=event_ids,
        backup_dir=backup_dir,
    )


__all__ = ["run_soak_test"]
