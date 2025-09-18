from __future__ import annotations

import pytest

from neuroca.memory.backends.vector.components.integrity import (
    VectorIndexIntegrityReport,
)
from neuroca.memory.manager.drift_monitor import EmbeddingDriftMonitor
from neuroca.memory.manager.events import EmbeddingDriftEvent, MaintenanceEventPublisher
from neuroca.memory.manager.metrics import MemoryMetricsPublisher


class _FakeVectorBackend:
    def __init__(self, report: VectorIndexIntegrityReport) -> None:
        self.report = report
        self.calls: list[dict[str, float | int | None]] = []

    async def check_index_integrity(
        self,
        *,
        drift_threshold: float = 0.1,
        sample_size: int | None = None,
    ) -> VectorIndexIntegrityReport:
        self.calls.append({"drift_threshold": drift_threshold, "sample_size": sample_size})
        return self.report


class _FakeExporter:
    def __init__(self) -> None:
        self.metrics: list[tuple[str, float, dict[str, str]]] = []

    def export_metric(
        self,
        name: str,
        value: float,
        *,
        labels: dict[str, str],
        metric_type,
    ) -> None:
        del metric_type
        self.metrics.append((name, value, labels))


class _Recorder:
    def __init__(self) -> None:
        self.events: list[object] = []

    async def publish(self, event: object) -> None:
        self.events.append(event)


class _FakeClock:
    def __init__(self, *, start: float) -> None:
        self._value = start

    def time(self) -> float:
        return self._value

    def advance(self, seconds: float) -> None:
        self._value += seconds


@pytest.mark.asyncio
async def test_monitor_requires_vector_backend() -> None:
    monitor = EmbeddingDriftMonitor.from_config({})
    result = await monitor.run_checks(quality_report={"drift": {"score": 0.7}}, force=True)
    assert result is None


@pytest.mark.asyncio
async def test_monitor_emits_metrics_and_events(monkeypatch: pytest.MonkeyPatch) -> None:
    from neuroca.memory.manager import drift_monitor as drift_module

    fake_clock = _FakeClock(start=1000.0)
    monkeypatch.setattr(drift_module, "time", fake_clock)

    integrity_report = VectorIndexIntegrityReport(
        index_entry_count=3,
        metadata_entry_count=3,
        checked_entry_count=3,
        drifted_ids=["alpha"],
        drift_scores={"alpha": 0.32},
        max_drift=0.32,
        avg_drift=0.21,
    )

    exporter = _FakeExporter()
    metrics = MemoryMetricsPublisher({"enabled": True}, exporter=exporter)

    recorder = _Recorder()
    events = MaintenanceEventPublisher({"enabled": True}, publisher=recorder.publish)

    monitor = EmbeddingDriftMonitor.from_config({"interval_seconds": 60})
    monitor.configure(
        vector_backend=_FakeVectorBackend(integrity_report),
        metrics=metrics,
        event_publisher=events,
    )

    quality_report = {"drift": {"score": 0.82}}
    result = await monitor.run_checks(quality_report=quality_report, force=True)

    assert result is not None
    assert result["alerts"]
    assert {alert["type"] for alert in result["alerts"]} == {
        "quality_drift",
        "vector_index_drift",
    }

    metric_names = {entry[0] for entry in exporter.metrics}
    assert "memory_embedding_drift_score" in metric_names
    assert "memory_vector_index_max_drift" in metric_names

    assert len(recorder.events) == 1
    assert isinstance(recorder.events[0], EmbeddingDriftEvent)

    # Re-running with the same data should not emit duplicate events.
    duplicate = await monitor.run_checks(quality_report=quality_report, force=True)
    assert duplicate is not None
    assert len(recorder.events) == 1


@pytest.mark.asyncio
async def test_monitor_respects_interval(monkeypatch: pytest.MonkeyPatch) -> None:
    from neuroca.memory.manager import drift_monitor as drift_module

    fake_clock = _FakeClock(start=500.0)
    monkeypatch.setattr(drift_module, "time", fake_clock)

    integrity_report = VectorIndexIntegrityReport(
        index_entry_count=5,
        metadata_entry_count=5,
        checked_entry_count=5,
        drifted_ids=[],
        max_drift=0.05,
        avg_drift=0.02,
    )

    monitor = EmbeddingDriftMonitor.from_config({"interval_seconds": 120})
    monitor.configure(
        vector_backend=_FakeVectorBackend(integrity_report),
        metrics=None,
        event_publisher=None,
    )

    first = await monitor.run_checks(quality_report={"drift": {"score": 0.4}})
    assert first is not None

    fake_clock.advance(30)
    skipped = await monitor.run_checks(quality_report={"drift": {"score": 0.45}})
    assert skipped is None

    fake_clock.advance(120)
    second = await monitor.run_checks(quality_report={"drift": {"score": 0.5}})
    assert second is not None

