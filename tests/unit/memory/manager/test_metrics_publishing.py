from __future__ import annotations

from typing import Any, Dict, List

import time

import pytest

from neuroca.memory.manager.metrics import MemoryMetricsPublisher
from neuroca.memory.manager.memory_manager import MemoryManager
from neuroca.monitoring.metrics.exporters import MetricType


class _RecordingExporter:
    """In-memory exporter used to capture emitted metrics during tests."""

    def __init__(self) -> None:
        self.records: List[Dict[str, Any]] = []

    def export_metric(
        self,
        name: str,
        value: float,
        labels: Dict[str, str] | None = None,
        metric_type: MetricType = MetricType.GAUGE,
        timestamp: float | None = None,
    ) -> None:  # pragma: no cover - signature compatibility only
        del timestamp
        self.records.append(
            {
                "name": name,
                "value": value,
                "labels": dict(labels or {}),
                "metric_type": metric_type,
            }
        )


def _latest(records: List[Dict[str, Any]], name: str, labels: Dict[str, str]) -> Dict[str, Any]:
    for record in reversed(records):
        if record["name"] == name and record["labels"] == labels:
            return record
    raise AssertionError(f"Metric {name} with labels {labels} not emitted")


def test_metrics_publisher_emits_expected_series() -> None:
    exporter = _RecordingExporter()
    publisher = MemoryMetricsPublisher(
        {"enabled": True},
        exporter=exporter,
    )

    publisher.record_consolidation(
        source="stm",
        target="mtm",
        duration_seconds=0.25,
        succeeded=True,
    )
    publisher.record_consolidation(
        source="mtm",
        target="ltm",
        duration_seconds=0.5,
        succeeded=False,
    )

    now = time.time()
    publisher.handle_cycle_report(
        {
            "consolidation": {"stm_to_mtm": 2, "mtm_to_ltm": 1, "total": 3},
            "duration_seconds": 6.0,
            "cleanup": {"stm": {"removed": 4}, "mtm": {"removed": 1}},
            "decay": {
                "stm": {"decayed": 2, "removed": 1},
                "mtm": {"decayed": 0, "removed": 0},
            },
            "telemetry": {
                "last_completed_at": now - 120,
                "last_started_at": now - 118,
            },
        }
    )

    publisher.update_capacity_snapshot(
        {"stm": {"ratio": 0.5}, "mtm": {"ratio": 0.25}, "ltm": {"ratio": 0.0}}
    )

    success_counter = _latest(
        exporter.records,
        "memory_consolidation_promotions_total",
        {"source": "stm", "target": "mtm"},
    )
    assert success_counter["value"] == pytest.approx(1.0)
    assert success_counter["metric_type"] is MetricType.COUNTER

    failure_counter = _latest(
        exporter.records,
        "memory_consolidation_failures_total",
        {"source": "mtm", "target": "ltm"},
    )
    assert failure_counter["value"] == pytest.approx(1.0)
    assert failure_counter["metric_type"] is MetricType.COUNTER

    latency_record = _latest(
        exporter.records,
        "memory_consolidation_latency_ms",
        {"source": "stm", "target": "mtm", "status": "success"},
    )
    assert latency_record["value"] == pytest.approx(250.0)
    assert latency_record["metric_type"] is MetricType.HISTOGRAM

    promotions_rate = _latest(
        exporter.records,
        "memory_promotions_per_second",
        {"path": "total"},
    )
    assert promotions_rate["value"] == pytest.approx(0.5)

    decay_total = _latest(
        exporter.records,
        "memory_decay_events_total",
        {"tier": "stm"},
    )
    assert decay_total["value"] == pytest.approx(3.0)
    assert decay_total["metric_type"] is MetricType.COUNTER

    orphan_total = _latest(
        exporter.records,
        "memory_orphaned_items",
        {"tier": "all"},
    )
    assert orphan_total["value"] == pytest.approx(5.0)
    assert orphan_total["metric_type"] is MetricType.GAUGE

    utilization_record = _latest(
        exporter.records,
        "memory_tier_utilization_percent",
        {"tier": "stm"},
    )
    assert utilization_record["value"] == pytest.approx(50.0)
    assert utilization_record["metric_type"] == MetricType.GAUGE

    backlog_metric = _latest(
        exporter.records,
        "memory_maintenance_backlog_age_seconds",
        {"scope": "maintenance"},
    )
    assert backlog_metric["value"] == pytest.approx(120.0, rel=0.05)
    assert backlog_metric["metric_type"] is MetricType.GAUGE


class _SimpleTier:
    def __init__(self) -> None:
        self.storage: Dict[str, Dict[str, Any]] = {}

    async def initialize(self) -> None:  # pragma: no cover - trivial setup
        return None

    async def store(self, payload: Dict[str, Any], memory_id: str | None = None) -> str:
        memory_id = memory_id or payload.get("id") or f"mem-{len(self.storage)}"
        record = dict(payload)
        record.setdefault("id", memory_id)
        self.storage[memory_id] = record
        return memory_id

    async def retrieve(self, memory_id: str) -> Dict[str, Any] | None:
        stored = self.storage.get(memory_id)
        return dict(stored) if stored else None

    async def delete(self, memory_id: str) -> bool:
        return self.storage.pop(memory_id, None) is not None

    async def shutdown(self) -> None:  # pragma: no cover - simple stub
        return None


@pytest.mark.asyncio
async def test_manager_consolidation_records_metrics() -> None:
    stm = _SimpleTier()
    mtm = _SimpleTier()
    ltm = _SimpleTier()
    manager = MemoryManager(
        config={"maintenance_interval": 0, "monitoring": {"metrics": {"enabled": False}}},
        stm=stm,
        mtm=mtm,
        ltm=ltm,
    )

    exporter = _RecordingExporter()
    manager._metrics = MemoryMetricsPublisher({"enabled": True}, exporter=exporter)

    await manager.initialize()

    await manager._stm.store(
        {
            "id": "memory-1",
            "content": {"text": "hello"},
            "metadata": {"importance": 0.9, "tags": {}},
        }
    )

    await manager.consolidate_memory("memory-1", source_tier="stm", target_tier="mtm")

    record = _latest(
        exporter.records,
        "memory_consolidation_promotions_total",
        {"source": "stm", "target": "mtm"},
    )
    assert record["value"] == pytest.approx(1.0)

    await manager.shutdown()
