"""Tests for the LTM snapshot exporter component."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from neuroca.memory.models.memory_item import (
    MemoryContent,
    MemoryItem,
    MemoryMetadata,
    MemoryStatus,
)
from neuroca.memory.tiers.ltm.components.lifecycle import LTMLifecycle
from neuroca.memory.tiers.ltm.components.snapshot import LTMSnapshotExporter


@pytest.fixture
def snapshot_exporter():
    backend = AsyncMock()
    lifecycle = MagicMock()
    exporter = LTMSnapshotExporter("ltm")
    exporter.configure(
        backend=backend,
        lifecycle=lifecycle,
        batch_size=1,
        clock=lambda: datetime(2024, 1, 1, tzinfo=timezone.utc),
    )
    return exporter, backend, lifecycle


def _memory_item(memory_id: str, *, status: MemoryStatus = MemoryStatus.ACTIVE) -> MemoryItem:
    return MemoryItem(
        id=memory_id,
        content=MemoryContent(text=f"memory {memory_id}"),
        metadata=MemoryMetadata(status=status, tags={"relationships": {}, "categories": ["general"]}),
    )


@pytest.mark.asyncio
async def test_export_snapshot_collects_batches(snapshot_exporter):
    exporter, backend, lifecycle = snapshot_exporter
    lifecycle.get_category_map.return_value = {"general": {"m1", "m2"}}
    lifecycle.get_relationship_map.return_value = {"m1": {"m2": 0.8}}

    first = _memory_item("m1").model_dump()
    second = _memory_item("m2", status=MemoryStatus.ARCHIVED).model_dump()

    backend.count.return_value = 2
    backend.query.side_effect = [[first], [second], []]

    snapshot = await exporter.export_snapshot()

    assert snapshot["tier"] == "ltm"
    assert snapshot["version"] == LTMSnapshotExporter.VERSION
    assert snapshot["count"] == 2
    assert snapshot["invalid"] == 0
    assert snapshot["categories"]["general"] == ["m1", "m2"]
    assert snapshot["relationships"] == {"m1": {"m2": 0.8}}

    # Ensure filters only include the expected default statuses
    filters = backend.query.call_args.kwargs["filters"]
    assert sorted(filters["metadata.status"]["$in"]) == sorted(
        [MemoryStatus.ACTIVE.value, MemoryStatus.ARCHIVED.value, MemoryStatus.CONSOLIDATED.value]
    )

    # Ensure batching advanced offsets
    assert backend.query.call_args_list[0].kwargs["offset"] == 0
    assert backend.query.call_args_list[1].kwargs["offset"] == 1


@pytest.mark.asyncio
async def test_export_snapshot_skips_invalid_items(snapshot_exporter):
    exporter, backend, lifecycle = snapshot_exporter
    lifecycle.get_category_map.return_value = {}
    lifecycle.get_relationship_map.return_value = {}

    backend.count.return_value = 1
    backend.query.side_effect = [[{"id": "missing-metadata"}], []]

    snapshot = await exporter.export_snapshot()

    assert snapshot["count"] == 0
    assert snapshot["invalid"] == 1


@pytest.mark.asyncio
async def test_restore_snapshot_creates_and_updates_records():
    backend = AsyncMock()
    lifecycle = LTMLifecycle("ltm")
    exporter = LTMSnapshotExporter("ltm")
    exporter.configure(backend=backend, lifecycle=lifecycle)

    first = _memory_item("m1")
    second = _memory_item("m2")

    backend.exists.side_effect = [False, True]
    backend.create.return_value = True
    backend.update.return_value = True

    snapshot = {
        "tier": "ltm",
        "memories": [first.model_dump(), second.model_dump()],
        "categories": {"general": ["m1", "m2"]},
        "relationships": {"m1": {"m2": 1.2}},
    }

    result = await exporter.restore_snapshot(snapshot, overwrite=True)

    assert result == {"restored": 2, "created": 1, "updated": 1, "skipped": 0, "invalid": 0}

    backend.create.assert_awaited_once()
    backend.update.assert_awaited_once()

    category_map = lifecycle.get_category_map()
    assert category_map == {"general": {"m1", "m2"}}

    relationship_map = lifecycle.get_relationship_map()
    assert relationship_map == {"m1": {"m2": 1.0}}


@pytest.mark.asyncio
async def test_restore_snapshot_skips_without_overwrite(snapshot_exporter):
    exporter, backend, lifecycle = snapshot_exporter
    lifecycle.apply_snapshot_state = MagicMock()

    item = _memory_item("m3")
    backend.exists.return_value = True

    snapshot = {"tier": "ltm", "memories": [item.model_dump()], "categories": {"general": ["m3"]}}

    result = await exporter.restore_snapshot(snapshot, overwrite=False)

    assert result == {"restored": 0, "created": 0, "updated": 0, "skipped": 1, "invalid": 0}
    backend.create.assert_not_called()
    backend.update.assert_not_called()
    lifecycle.apply_snapshot_state.assert_called_once()
