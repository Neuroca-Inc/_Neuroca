"""Data structures used by the memory soak-test harness."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Mapping, Optional


@dataclass
class SoakTestReport:
    """Structured metrics captured from a soak-test execution.

    Attributes:
        duration_seconds: Total runtime in seconds for the exercised workload.
        operations_performed: Count of memory operations executed (CRUD,
            consolidation, decay).
        maintenance_cycles: Number of promotion/decay batches processed.
        promotions: Total tier promotions performed during the run.
        promotions_per_second: Promotion throughput calculated over the
            measured duration.
        decay_events: Counter keyed by tier recording decay invocations.
        backlog_age_seconds: Age of the stalest memory interaction captured in
            the run; higher numbers imply deeper backlogs.
        audit_event_count: Number of audit events emitted by the manager.
        duplicate_event_ids: Count of duplicate event identifiers detected,
            signalling idempotency issues if non-zero.
        backup_path: Location of the generated snapshot when the caller opts to
            persist it, otherwise ``None`` when a temporary directory was used.
        restore_valid: ``True`` when the backup round-trip recreates all
            memories in a fresh manager instance.
        errors: Collection of high-level error strings gathered during the run.
    """

    duration_seconds: float
    operations_performed: int
    maintenance_cycles: int
    promotions: int
    promotions_per_second: float
    decay_events: Mapping[str, int]
    backlog_age_seconds: float
    audit_event_count: int
    duplicate_event_ids: int
    backup_path: Optional[Path]
    restore_valid: bool
    errors: List[str]


__all__ = ["SoakTestReport"]
