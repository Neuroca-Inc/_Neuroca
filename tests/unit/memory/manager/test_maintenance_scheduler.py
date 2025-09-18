from __future__ import annotations

import asyncio
import contextlib
from datetime import datetime, timedelta, timezone
import logging
from typing import Any, Dict, List, Optional

import pytest

from neuroca.memory.manager.maintenance import MaintenanceOrchestrator
from neuroca.memory.manager.memory_manager import MemoryManager
from neuroca.memory.manager.events import (
    ConsolidationOutcomeEvent,
    MaintenanceCycleEvent,
    MaintenanceEventPublisher,
)


class _StubTier:
    def __init__(self, name: str) -> None:
        self.name = name
        self.storage: Dict[str, Dict[str, Any]] = {}
        self.query_results: List[Dict[str, Any]] = []
        self.promotion_candidates: List[Dict[str, Any]] = []
        self.maintenance_calls = 0
        self.cleanup_calls = 0
        self.cleanup_return = 0
        self.fail_maintenance = False
        self.fail_cleanup = False

    async def initialize(self) -> None:  # pragma: no cover - simple stub
        return None

    async def shutdown(self) -> None:  # pragma: no cover - simple stub
        return None

    async def run_maintenance(self) -> Dict[str, Any]:
        self.maintenance_calls += 1
        if self.fail_maintenance:
            raise RuntimeError(f"{self.name} maintenance failure")
        return {"tier": self.name, "runs": self.maintenance_calls}

    async def cleanup(self) -> int:
        self.cleanup_calls += 1
        if self.fail_cleanup:
            raise RuntimeError(f"{self.name} cleanup failure")
        return self.cleanup_return

    async def store(self, payload: Dict[str, Any], memory_id: Optional[str] = None) -> str:
        memory_id = memory_id or payload.get("id") or f"{self.name}-{len(self.storage)}"
        stored = dict(payload)
        stored.setdefault("id", memory_id)
        metadata = stored.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}
        metadata.setdefault("tags", {})
        stored["metadata"] = metadata
        self.storage[memory_id] = stored
        return memory_id

    async def retrieve(self, memory_id: str) -> Optional[Dict[str, Any]]:
        return self.storage.get(memory_id)

    async def delete(self, memory_id: str) -> bool:
        return self.storage.pop(memory_id, None) is not None

    async def query(
        self,
        filters: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        del filters, limit
        return list(self.query_results)

    async def get_promotion_candidates(self, limit: int = 10) -> List[Dict[str, Any]]:
        return list(self.promotion_candidates)[:limit]

    async def list_all(self) -> List[Dict[str, Any]]:  # pragma: no cover - compatibility
        return list(self.storage.values())


class _CountingDecay:
    def __init__(self, payload: Optional[Dict[str, Any]] = None) -> None:
        self.payload = payload or {"status": "ok"}
        self.calls = 0

    async def __call__(self) -> Dict[str, Any]:
        self.calls += 1
        return self.payload


async def _build_manager(
    *,
    event_recorder: List[Any] | None = None,
    config_override: Optional[Dict[str, Any]] = None,
) -> tuple[MemoryManager, Dict[str, _StubTier]]:
    tiers = {name: _StubTier(name) for name in ("stm", "mtm", "ltm")}
    base_config: Dict[str, Any] = {
        "maintenance_interval": 0,
        "stm": {},
        "mtm": {},
        "ltm": {},
        "maintenance": {},
    }

    if config_override:
        merged: Dict[str, Any] = dict(base_config)
        for key, value in config_override.items():
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                nested = dict(merged[key])  # type: ignore[index]
                nested.update(value)
                merged[key] = nested
            else:
                merged[key] = value
        base_config = merged

    manager = MemoryManager(
        config=base_config,
        stm=tiers["stm"],
        mtm=tiers["mtm"],
        ltm=tiers["ltm"],
    )
    if event_recorder is not None:
        async def _publish(event: Any) -> None:
            event_recorder.append(event)

        manager._event_publisher = MaintenanceEventPublisher(
            {"enabled": True},
            log=logging.getLogger("test.maintenance.events"),
            publisher=_publish,
        )
    await manager.initialize()
    return manager, tiers


@pytest.mark.asyncio
async def test_orchestrator_runs_full_cycle_and_reports_success() -> None:
    events: List[Any] = []
    manager, tiers = await _build_manager(event_recorder=events)
    stm, mtm, ltm = tiers["stm"], tiers["mtm"], tiers["ltm"]

    mtm_decay = _CountingDecay({"processed": 3})
    ltm_decay = _CountingDecay({"processed": 2})
    orchestrator = MaintenanceOrchestrator(
        manager,
        min_interval=10.0,
        decay_handlers={"mtm": mtm_decay, "ltm": ltm_decay},
        event_publisher=manager._event_publisher,
    )
    manager._maintenance_orchestrator = orchestrator

    await stm.store(
        {
            "id": "stm-candidate",
            "content": {"text": "short term"},
            "metadata": {"importance": 0.9, "tags": {}, "access_count": 7},
            "access_count": 7,
        }
    )
    stm.query_results = [dict(stm.storage["stm-candidate"], access_count=7)]

    await mtm.store(
        {
            "id": "mtm-candidate",
            "content": {"text": "medium term"},
            "metadata": {"importance": 0.85, "tags": {}},
        }
    )
    mtm.promotion_candidates = [{"id": "mtm-candidate"}]

    stm.cleanup_return = 1
    mtm.cleanup_return = 2
    ltm.cleanup_return = 3

    try:
        result = await orchestrator.run_cycle(triggered_by="test")
    finally:
        await manager.shutdown()

    assert result["status"] == "ok"
    assert result["consolidated_memories"] == 2
    assert result["consolidation"]["stm_to_mtm"] == 1
    assert result["consolidation"]["mtm_to_ltm"] == 1
    assert result["cleanup"]["stm"]["removed"] == 1
    assert result["cleanup"]["mtm"]["removed"] == 2
    assert result["decay"]["mtm"] == {"status": "ok", "processed": 3}
    assert result["decay"]["ltm"] == {"status": "ok", "processed": 2}
    assert mtm_decay.calls == 1
    assert ltm_decay.calls == 1
    assert orchestrator.telemetry.successful_cycles == 1
    assert orchestrator.telemetry.consecutive_failures == 0
    assert "telemetry" in result
    assert "stm-candidate" not in stm.storage
    assert "mtm-candidate" not in mtm.storage
    assert "mtm-candidate" in ltm.storage

    cycle_events = [event for event in events if isinstance(event, MaintenanceCycleEvent)]
    assert len(cycle_events) == 2
    assert cycle_events[0].status == "started"
    assert cycle_events[1].status == "ok"
    assert cycle_events[1].consolidation_summary["total"] == 2

    consolidation_events = [
        event for event in events if isinstance(event, ConsolidationOutcomeEvent)
    ]
    assert consolidation_events and all(event.status == "success" for event in consolidation_events)


@pytest.mark.asyncio
async def test_orchestrator_records_failures_and_adjusts_delay() -> None:
    manager, tiers = await _build_manager()
    mtm_decay = _CountingDecay()
    ltm_decay = _CountingDecay()
    orchestrator = MaintenanceOrchestrator(
        manager,
        min_interval=10.0,
        decay_handlers={"mtm": mtm_decay, "ltm": ltm_decay},
    )
    manager._maintenance_orchestrator = orchestrator

    tiers["mtm"].fail_maintenance = True

    try:
        result = await orchestrator.run_cycle(triggered_by="test")
        assert result["status"] == "error"
        assert any("mtm" in error for error in result.get("errors", []))
        assert orchestrator.telemetry.consecutive_failures == 1

        delay = orchestrator.compute_next_delay(120.0)
        assert delay == pytest.approx(max(10.0, 120.0 / 2))

        tiers["mtm"].fail_maintenance = False
        recovery = await orchestrator.run_cycle(triggered_by="test")
        assert recovery["status"] == "ok"
        assert orchestrator.telemetry.consecutive_failures == 0
        assert orchestrator.compute_next_delay(120.0) == pytest.approx(120.0)
    finally:
        await manager.shutdown()


@pytest.mark.asyncio
async def test_shutdown_waits_for_background_maintenance_cycle() -> None:
    tiers = {name: _StubTier(name) for name in ("stm", "mtm", "ltm")}
    manager = MemoryManager(
        config={"maintenance_interval": 0, "stm": {}, "mtm": {}, "ltm": {}},
        stm=tiers["stm"],
        mtm=tiers["mtm"],
        ltm=tiers["ltm"],
    )

    manager._maintenance_retry_interval = 0.05
    manager._shutdown_drain_timeout = 1.0
    await manager.initialize()

    manager._maintenance_interval = 0.05
    orchestrator = manager._ensure_maintenance_orchestrator()

    cycle_started = asyncio.Event()
    release_cycle = asyncio.Event()

    async def blocking_cycle(*, triggered_by: str) -> Dict[str, Any]:
        cycle_started.set()
        await release_cycle.wait()
        return {
            "status": "ok",
            "errors": [],
            "consolidation": {"stm_to_mtm": 0, "mtm_to_ltm": 0, "total": 0},
        }

    orchestrator.run_cycle = blocking_cycle  # type: ignore[assignment]

    manager._start_maintenance_task()

    await asyncio.wait_for(cycle_started.wait(), timeout=1.0)

    shutdown_task = asyncio.create_task(manager.shutdown())
    try:
        await asyncio.sleep(0)
        assert not shutdown_task.done()

        release_cycle.set()

        await asyncio.wait_for(shutdown_task, timeout=1.0)
    finally:
        release_cycle.set()
        if not shutdown_task.done():
            shutdown_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await shutdown_task


@pytest.mark.asyncio
async def test_quality_analysis_attached_to_maintenance_report() -> None:
    manager, tiers = await _build_manager()
    orchestrator = MaintenanceOrchestrator(manager, min_interval=5.0)
    manager._maintenance_orchestrator = orchestrator

    now = datetime.now(timezone.utc)
    stale = now - timedelta(days=60)

    sample_payloads = [
        {
            "id": "alpha-1",
            "content": {"text": "Alpha project roadmap"},
            "metadata": {
                "last_accessed": (stale - timedelta(days=2)).isoformat(),
                "tags": {"cluster": "alpha"},
            },
            "embedding": [0.1, 0.1, 0.1],
        },
        {
            "id": "alpha-2",
            "content": {"text": "Alpha project roadmap"},
            "metadata": {
                "last_accessed": (stale - timedelta(days=1)).isoformat(),
                "tags": {"cluster": "alpha"},
            },
            "embedding": [0.12, 0.1, 0.09],
        },
        {
            "id": "alpha-3",
            "content": {"text": "Alpha project roadmapping details"},
            "metadata": {
                "last_accessed": (stale - timedelta(days=5)).isoformat(),
                "tags": {"cluster": "alpha"},
            },
            "embedding": [0.11, 0.09, 0.11],
        },
        {
            "id": "beta-1",
            "content": {"text": "Completely unrelated beta summary"},
            "metadata": {
                "last_accessed": now.isoformat(),
                "tags": {"cluster": "beta"},
            },
            "embedding": [1.0, -1.0, 1.0],
        },
    ]

    for payload in sample_payloads:
        await tiers["ltm"].store(payload)

    result = await orchestrator.run_cycle(triggered_by="quality-test")

    assert result["status"] == "ok"
    quality = result.get("quality")
    assert quality is not None
    assert quality["total_memories"] == len(sample_payloads)
    assert quality["metrics"]["redundancy_ratio"] > 0
    assert quality["metrics"]["stale_ratio"] > 0
    assert quality["metrics"]["drift_score"] > 0
    alert_types = {alert["type"] for alert in quality["alerts"]}
    assert "redundancy" in alert_types
    assert any(kind in alert_types for kind in {"stale", "stale_cluster"})
    assert "embedding_drift" in alert_types
    assert manager.last_quality_report is not None
    assert manager.last_quality_report["total_memories"] == len(sample_payloads)



@pytest.mark.asyncio
async def test_consolidation_skips_when_circuit_breaker_reports_backlog() -> None:
    manager, _ = await _build_manager(
        config_override={
            "maintenance": {
                "circuit_breaker": {
                    "queued_backlog_threshold": 1,
                    "failure_threshold": 5,
                    "cooldown_seconds": 60.0,
                }
            }
        }
    )
    orchestrator = MaintenanceOrchestrator(manager, min_interval=5.0)
    manager._maintenance_orchestrator = orchestrator

    original_snapshot = manager._backpressure.snapshot
    manager._backpressure.snapshot = lambda: {  # type: ignore[assignment]
        "stm": {"queued": 3, "inflight": 1},
        "mtm": {"queued": 0, "inflight": 0},
        "ltm": {"queued": 0, "inflight": 0},
    }

    try:
        result = await orchestrator.run_cycle(triggered_by="breaker-backlog")
    finally:
        manager._backpressure.snapshot = original_snapshot  # type: ignore[assignment]
        await manager.shutdown()

    consolidation = result["consolidation"]
    assert consolidation.get("status") == "circuit_open"
    skipped = consolidation.get("skipped")
    assert skipped is not None
    assert skipped["queued_backlog"] == 3
    assert "queued backlog" in (skipped.get("reason") or "")
    assert consolidation["total"] == 0


@pytest.mark.asyncio
async def test_circuit_breaker_releases_after_failures_clear() -> None:
    manager, tiers = await _build_manager(
        config_override={
            "maintenance": {
                "circuit_breaker": {
                    "failure_threshold": 1,
                    "cooldown_seconds": 0.0,
                }
            }
        }
    )
    orchestrator = MaintenanceOrchestrator(manager, min_interval=5.0)
    manager._maintenance_orchestrator = orchestrator

    orchestrator.telemetry.consecutive_failures = 2

    try:
        first = await orchestrator.run_cycle(triggered_by="breaker-failure")

        consolidation = first["consolidation"]
        assert consolidation.get("status") == "circuit_open"
        skipped = consolidation.get("skipped")
        assert skipped is not None
        assert skipped["consecutive_failures"] == 2

        orchestrator.telemetry.consecutive_failures = 0
        manager._backpressure.snapshot = lambda: {  # type: ignore[assignment]
            "stm": {"queued": 0, "inflight": 0},
            "mtm": {"queued": 0, "inflight": 0},
            "ltm": {"queued": 0, "inflight": 0},
        }

        stm, mtm = tiers["stm"], tiers["mtm"]
        await stm.store(
            {
                "id": "stm-sample",
                "content": {"text": "short"},
                "metadata": {"importance": 0.9, "tags": {}},
                "access_count": 9,
            }
        )
        stm.query_results = [dict(stm.storage["stm-sample"], access_count=9)]
        await mtm.store(
            {
                "id": "mtm-sample",
                "content": {"text": "medium"},
                "metadata": {"importance": 0.85, "tags": {}},
            }
        )
        mtm.promotion_candidates = [{"id": "mtm-sample"}]

        second = await orchestrator.run_cycle(triggered_by="breaker-recovered")
    finally:
        await manager.shutdown()

    consolidation_two = second["consolidation"]
    assert consolidation_two.get("status") != "circuit_open"
    assert consolidation_two["total"] >= 0
