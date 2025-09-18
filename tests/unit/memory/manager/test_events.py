from typing import Any, List

import pytest

from neuroca.memory.manager.events import (
    ConsolidationOutcomeEvent,
    EmbeddingDriftEvent,
    MaintenanceCycleEvent,
    MaintenanceEventPublisher,
)


class _Recorder:
    def __init__(self) -> None:
        self.events: List[Any] = []

    async def publish(self, event: Any) -> None:
        self.events.append(event)


@pytest.mark.asyncio
async def test_cycle_events_capture_structured_payload() -> None:
    recorder = _Recorder()
    publisher = MaintenanceEventPublisher({"enabled": True}, publisher=recorder.publish)

    await publisher.cycle_started(cycle_id="cycle-1", triggered_by="manual")
    await publisher.cycle_completed(
        cycle_id="cycle-1",
        triggered_by="manual",
        report={
            "status": "ok",
            "duration_seconds": 1.5,
            "errors": [],
            "consolidation": {"total": 3},
            "decay": {"ltm": {"decayed": 2}},
            "telemetry": {"cycles": 4},
        },
    )

    cycle_events = [event for event in recorder.events if isinstance(event, MaintenanceCycleEvent)]
    assert len(cycle_events) == 2

    started, completed = cycle_events
    assert started.status == "started"
    assert started.metadata["cycle_id"] == "cycle-1"

    assert completed.status == "ok"
    assert completed.metadata["consolidation"]["total"] == 3
    assert completed.metadata["telemetry"]["cycles"] == 4
    assert completed.duration_seconds == pytest.approx(1.5)


@pytest.mark.asyncio
async def test_consolidation_event_records_errors() -> None:
    recorder = _Recorder()
    publisher = MaintenanceEventPublisher({"enabled": True}, publisher=recorder.publish)

    await publisher.consolidation_completed(
        memory_id="mtm-1",
        source_tier="mtm",
        target_tier="ltm",
        status="error",
        duration_seconds=0.2,
        result_id=None,
        error="vector backend timeout",
    )

    outcome_events = [event for event in recorder.events if isinstance(event, ConsolidationOutcomeEvent)]
    assert len(outcome_events) == 1
    event = outcome_events[0]
    assert event.status == "error"
    assert event.metadata["error"] == "vector backend timeout"
    assert event.metadata["duration_seconds"] == pytest.approx(0.2)


@pytest.mark.asyncio
async def test_disabled_publisher_drops_events() -> None:
    recorder = _Recorder()
    publisher = MaintenanceEventPublisher({"enabled": False}, publisher=recorder.publish)

    await publisher.cycle_started(cycle_id="cycle-2", triggered_by="scheduler")
    await publisher.consolidation_completed(
        memory_id="cached",
        source_tier="stm",
        target_tier="mtm",
        status="success",
        duration_seconds=0.1,
        result_id="mtm-9",
    )

    assert recorder.events == []


@pytest.mark.asyncio
async def test_embedding_drift_event_carries_alert_metadata() -> None:
    recorder = _Recorder()
    publisher = MaintenanceEventPublisher({"enabled": True}, publisher=recorder.publish)

    alerts = [{"type": "vector_index_drift", "severity": "warning", "drifted_ids": ["x"]}]
    await publisher.embedding_drift_detected(
        alerts=alerts,
        quality_summary={"drift": {"score": 0.7}},
        integrity_summary={"max_drift": 0.3, "drifted_ids": ["x"]},
        quality_score=0.7,
        quality_delta=0.2,
        max_drift=0.3,
    )

    assert recorder.events
    event = recorder.events[0]
    assert isinstance(event, EmbeddingDriftEvent)
    assert event.metadata["alerts"][0]["type"] == "vector_index_drift"
    assert event.metadata["max_drift"] == pytest.approx(0.3)


@pytest.mark.asyncio
async def test_publisher_enforces_idempotent_emission() -> None:
    recorder = _Recorder()
    publisher = MaintenanceEventPublisher(
        {"enabled": True, "dedupe_ttl_seconds": 120, "dedupe_max_entries": 16},
        publisher=recorder.publish,
    )

    await publisher.consolidation_completed(
        memory_id="mem-1",
        source_tier="stm",
        target_tier="mtm",
        status="success",
        duration_seconds=0.4,
        result_id="mtm-1",
    )
    await publisher.consolidation_completed(
        memory_id="mem-1",
        source_tier="stm",
        target_tier="mtm",
        status="success",
        duration_seconds=0.4,
        result_id="mtm-1",
    )
    await publisher.consolidation_completed(
        memory_id="mem-1",
        source_tier="stm",
        target_tier="mtm",
        status="error",
        duration_seconds=0.6,
        result_id=None,
        error="timeout",
    )

    outcome_events = [event for event in recorder.events if isinstance(event, ConsolidationOutcomeEvent)]
    assert len(outcome_events) == 2
    assert [event.status for event in outcome_events] == ["success", "error"]


@pytest.mark.asyncio
async def test_publisher_assigns_deterministic_event_ids() -> None:
    first_recorder = _Recorder()
    first_publisher = MaintenanceEventPublisher(
        {"enabled": True},
        publisher=first_recorder.publish,
    )

    await first_publisher.consolidation_completed(
        memory_id="mem-42",
        source_tier="stm",
        target_tier="ltm",
        status="success",
        duration_seconds=1.2,
        result_id="ltm-42",
    )

    assert first_recorder.events
    first_event = first_recorder.events[0]

    second_recorder = _Recorder()
    second_publisher = MaintenanceEventPublisher(
        {"enabled": True},
        publisher=second_recorder.publish,
    )

    await second_publisher.consolidation_completed(
        memory_id="mem-42",
        source_tier="stm",
        target_tier="ltm",
        status="success",
        duration_seconds=1.2,
        result_id="ltm-42",
    )

    assert second_recorder.events
    assert second_recorder.events[0].id == first_event.id
