import json
import logging
from typing import Any, List

import pytest

from neuroca.memory.manager.audit import MemoryAuditTrail
from neuroca.memory.manager.scoping import MemoryRetrievalScope
from neuroca.memory.models.memory_item import MemoryItem, MemoryMetadata


class _ListHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.records: List[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:  # pragma: no cover - logging hook
        self.records.append(record)


def _capture_logger() -> tuple[logging.Logger, _ListHandler]:
    logger = logging.getLogger("test.memory.audit")
    logger.setLevel(logging.INFO)
    handler = _ListHandler()
    logger.addHandler(handler)
    return logger, handler


def _release_logger(logger: logging.Logger, handler: _ListHandler) -> None:
    logger.removeHandler(handler)


@pytest.mark.asyncio
async def test_record_creation_redacts_sensitive_text() -> None:
    logger, handler = _capture_logger()
    published: List[Any] = []

    async def _publish(event: Any) -> None:
        published.append(event)

    trail = MemoryAuditTrail(log=logger, publisher=_publish)

    memory = MemoryItem(
        content={"text": "super secret text", "summary": "classified"},
        metadata=MemoryMetadata(
            importance=0.9,
            user_id="user-123",
            additional_metadata={"notes": "should not leak"},
        ),
    )

    try:
        await trail.record_creation(memory, tier="stm", scope=MemoryRetrievalScope.for_user("user-123"))
    finally:
        _release_logger(logger, handler)

    assert handler.records, "expected audit log entry to be recorded"
    message = handler.records[0].getMessage()
    assert "super secret text" not in message
    assert "classified" not in message
    assert "should not leak" not in message

    _, payload = message.split(" | ", 1)
    serialized = json.loads(payload)
    assert serialized["action"] == "memory.created"
    assert serialized["metadata_snapshot"]["tags"]["count"] == 0
    assert serialized["scope"]["user_id"] == "user-123"

    assert published, "expected MemoryCreatedEvent to be emitted"
    event = published[0]
    assert event.memory_id == memory.id
    assert event.metadata["tier"] == "stm"
    assert event.metadata["scope"]["user_id"] == "user-123"
    assert "text_length" in event.content
    assert "text" not in event.content


@pytest.mark.asyncio
async def test_record_consolidation_emits_event_with_context() -> None:
    logger, handler = _capture_logger()
    published: List[Any] = []

    async def _publish(event: Any) -> None:
        published.append(event)

    trail = MemoryAuditTrail(log=logger, publisher=_publish)

    source_memory = MemoryItem(
        content={"text": "older memory payload"},
        metadata=MemoryMetadata(
            importance=0.7,
            tags={"topic": "ops"},
            user_id="user-456",
        ),
    )

    try:
        await trail.record_consolidation(
            source_memory,
            source_tier="stm",
            target_tier="mtm",
            new_memory_id="mtm-abc",
        )
    finally:
        _release_logger(logger, handler)

    assert handler.records
    message = handler.records[0].getMessage()
    assert "older memory payload" not in message

    _, payload = message.split(" | ", 1)
    serialized = json.loads(payload)
    assert serialized["action"] == "memory.consolidated"
    assert serialized["metadata_snapshot"]["tags"]["count"] == 1

    assert published
    event = published[0]
    assert event.memory_id == "mtm-abc"
    assert event.metadata["source_tier"] == "stm"
    assert event.metadata["target_tier"] == "mtm"
    assert event.metadata["source_memory_id"] == source_memory.id
    assert "older memory payload" not in json.dumps(event.content)


@pytest.mark.asyncio
async def test_audit_trail_deduplicates_events() -> None:
    logger, handler = _capture_logger()
    published: List[Any] = []

    async def _publish(event: Any) -> None:
        published.append(event)

    trail = MemoryAuditTrail(log=logger, publisher=_publish)

    memory = MemoryItem(
        content={"text": "duplicate payload"},
        metadata=MemoryMetadata(importance=0.5),
    )

    try:
        await trail.record_creation(memory, tier="stm")
        await trail.record_creation(memory, tier="stm")
    finally:
        _release_logger(logger, handler)

    assert len(published) == 1
    assert len(handler.records) == 1


@pytest.mark.asyncio
async def test_audit_trail_assigns_stable_event_ids() -> None:
    memory = MemoryItem(
        content={"text": "stable id"},
        metadata=MemoryMetadata(importance=0.6),
    )

    first_logger, first_handler = _capture_logger()
    first_published: List[Any] = []

    async def _publish_first(event: Any) -> None:
        first_published.append(event)

    trail_one = MemoryAuditTrail(log=first_logger, publisher=_publish_first)

    try:
        await trail_one.record_creation(memory, tier="stm")
    finally:
        _release_logger(first_logger, first_handler)

    assert first_published
    recorded_id = first_published[0].id

    second_logger, second_handler = _capture_logger()
    second_published: List[Any] = []

    async def _publish_second(event: Any) -> None:
        second_published.append(event)

    trail_two = MemoryAuditTrail(log=second_logger, publisher=_publish_second)

    try:
        await trail_two.record_creation(memory, tier="stm")
    finally:
        _release_logger(second_logger, second_handler)

    assert second_published
    assert second_published[0].id == recorded_id
