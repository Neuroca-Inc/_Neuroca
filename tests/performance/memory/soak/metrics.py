"""Metric helpers for the soak-test harness."""

from __future__ import annotations

import time
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

from .models import SoakTestReport


def _calculate_backlog_age(last_access: Mapping[str, float]) -> float:
    """Compute backlog age from the ``last_access`` mapping.

    Args:
        last_access: Mapping of memory identifiers to the most recent access
            timestamps captured via :func:`time.perf_counter`.

    Returns:
        Age, in seconds, of the stalest interaction or ``0.0`` when no
        memories were tracked.
    """

    if not last_access:
        return 0.0
    now = time.perf_counter()
    return max(0.0, max(now - timestamp for timestamp in last_access.values()))


def _promotion_metrics(promotions: Counter, duration: float) -> tuple[int, float]:
    """Compute total promotions and throughput given ``duration`` seconds.

    Args:
        promotions: Counter tracking promotion events.
        duration: Total elapsed duration, in seconds, for the soak run.

    Returns:
        Tuple containing the promotion count and derived throughput.
    """

    total = sum(promotions.values())
    rate = total / duration if duration > 0 else 0.0
    return total, rate


def _build_report(
    *,
    duration_seconds: float,
    operations: int,
    cycles: int,
    total_promotions: int,
    promotion_rate: float,
    decay_counts: Counter,
    backlog_age: float,
    audit_events: Sequence[Any],
    duplicate_ids: int,
    snapshot_path: Optional[Path],
    restore_valid: bool,
    errors: Sequence[str],
) -> SoakTestReport:
    """Assemble the final :class:`SoakTestReport` payload.

    Args:
        duration_seconds: Total duration of the soak run in seconds.
        operations: Number of operations executed during the run.
        cycles: Number of workload cycles completed.
        total_promotions: Total number of promotions observed.
        promotion_rate: Promotion throughput in promotions per second.
        decay_counts: Counter describing decay activity per tier.
        backlog_age: Age of the stalest memory interaction in seconds.
        audit_events: Sequence of captured audit events.
        duplicate_ids: Number of duplicate audit event identifiers observed.
        snapshot_path: Optional path where the snapshot was preserved.
        restore_valid: ``True`` when the restore round-trip succeeded.
        errors: Sequence of error strings captured during the run.

    Returns:
        Populated :class:`SoakTestReport` instance summarising the run.
    """

    return SoakTestReport(
        duration_seconds=duration_seconds,
        operations_performed=operations,
        maintenance_cycles=cycles,
        promotions=total_promotions,
        promotions_per_second=promotion_rate,
        decay_events=dict(decay_counts),
        backlog_age_seconds=backlog_age,
        audit_event_count=len(audit_events),
        duplicate_event_ids=max(0, duplicate_ids),
        backup_path=snapshot_path,
        restore_valid=restore_valid,
        errors=[str(entry) for entry in errors],
    )


__all__ = [
    "_calculate_backlog_age",
    "_promotion_metrics",
    "_build_report",
]
