"""Memory manager helpers for the soak-test harness."""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from neuroca.memory.backends.factory.backend_type import BackendType
from neuroca.memory.manager.audit import MemoryAuditTrail
from neuroca.memory.manager.memory_manager import MemoryManager


def _default_manager_config(maintenance_interval: float) -> Dict[str, Any]:
    """Build a minimal memory-manager configuration for soak testing.

    Args:
        maintenance_interval: Base interval, in seconds, for background
            maintenance scheduling.

    Returns:
        Dictionary containing configuration values that disable metrics and
        events while keeping consolidation control predictable for the harness.
    """

    return {
        "maintenance_interval": float(max(0.0, maintenance_interval)),
        "monitoring": {
            "metrics": {"enabled": False},
            "events": {"enabled": False},
        },
        "maintenance": {
            "stm_to_mtm_batch_size": 0,
            "mtm_to_ltm_batch_size": 0,
        },
    }


def _initial_state() -> Dict[str, Any]:
    """Create the mutable state dictionary for soak-test bookkeeping.

    Returns:
        Dictionary prepopulated with counters and identifier buffers used by
        the soak harness to track operations and tier membership.
    """

    return {
        "operations": 0,
        "stm_ids": [],
        "mtm_ids": [],
        "ltm_ids": [],
        "all_ids": set(),
        "last_access": {},
        "errors": [],
    }


def _capture_audit_events(buffer: List[Any], ids: List[str]):
    """Create an asynchronous publisher that records emitted audit events.

    Args:
        buffer: Mutable list used to collect event objects for later analysis.
        ids: Mutable list used to capture emitted event identifiers.

    Returns:
        Awaitable callback compatible with :class:`MemoryAuditTrail`.
    """

    async def _publisher(event: Any) -> None:
        identifier = getattr(event, "id", None)
        if identifier is not None:
            ids.append(str(identifier))
        buffer.append(event)

    return _publisher


async def _initialise_manager(
    maintenance_interval: float,
    *,
    audit_events: List[Any],
    event_ids: List[str],
) -> MemoryManager:
    """Initialise the memory manager with metrics/event publishing disabled.

    Args:
        maintenance_interval: Base interval, in seconds, for maintenance loops.
        audit_events: Collection that will be populated with emitted audit events.
        event_ids: Collection that tracks audit event identifiers for
            idempotency validation.

    Returns:
        Configured :class:`MemoryManager` instance ready for soak testing.

    Side Effects:
        Starts the memory manager and attaches a custom audit publisher.
    """

    manager = MemoryManager(
        backend_type=BackendType.MEMORY,
        config=_default_manager_config(maintenance_interval),
    )
    await manager.initialize()
    manager._audit_trail = MemoryAuditTrail(  # type: ignore[attr-defined]
        log=logging.getLogger("tests.performance.memory.soak.audit"),
        publisher=_capture_audit_events(audit_events, event_ids),
    )
    return manager


__all__ = [
    "_default_manager_config",
    "_initial_state",
    "_initialise_manager",
    "_capture_audit_events",
]
