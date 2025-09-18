"""Snapshot export and restore helpers for the LTM tier."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Callable, Iterable, Mapping, Sequence

from pydantic import ValidationError

from neuroca.memory.backends import BaseStorageBackend
from neuroca.memory.models.memory_item import MemoryItem, MemoryStatus
from neuroca.memory.tiers.ltm.components.lifecycle import LTMLifecycle


logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    """Return a timezone-aware UTC timestamp."""

    return datetime.now(timezone.utc)


class LTMSnapshotExporter:
    """Export and restore long-term memory snapshots for redundancy paths."""

    VERSION = 1
    DEFAULT_BATCH_SIZE = 500
    DEFAULT_STATUSES: Sequence[MemoryStatus] = (
        MemoryStatus.ACTIVE,
        MemoryStatus.ARCHIVED,
        MemoryStatus.CONSOLIDATED,
    )

    def __init__(self, tier_name: str) -> None:
        self._tier_name = tier_name
        self._backend: BaseStorageBackend | None = None
        self._lifecycle: LTMLifecycle | None = None
        self._batch_size = self.DEFAULT_BATCH_SIZE
        self._clock: Callable[[], datetime] = _utcnow

    def configure(
        self,
        *,
        backend: BaseStorageBackend,
        lifecycle: LTMLifecycle | None = None,
        batch_size: int | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        """Configure exporter dependencies."""

        self._backend = backend
        self._lifecycle = lifecycle
        if batch_size is not None and batch_size > 0:
            self._batch_size = batch_size
        if clock is not None:
            self._clock = clock

    async def export_snapshot(
        self,
        *,
        statuses: Iterable[MemoryStatus | str] | None = None,
        limit: int | None = None,
        batch_size: int | None = None,
    ) -> dict[str, Any]:
        """Collect a redundancy snapshot of LTM memories."""

        backend = self._require_backend()
        filters = self._build_filters(statuses)
        requested_batch = self._resolve_batch_size(batch_size)

        total_count: int | None = None
        try:
            total_count = await backend.count(filters or None)
        except Exception:  # pragma: no cover - defensive logging path
            logger.warning("Failed to count LTM records before export", exc_info=True)

        offset = 0
        collected: list[dict[str, Any]] = []
        invalid = 0

        while True:
            remaining = None if limit is None else max(0, limit - len(collected))
            if remaining == 0:
                break

            batch_limit = requested_batch if remaining is None else min(requested_batch, remaining)
            items = await backend.query(
                filters=filters or None,
                sort_by="metadata.created_at",
                ascending=True,
                limit=batch_limit,
                offset=offset,
            )
            if not items:
                break

            offset += len(items)

            for raw in items:
                try:
                    item = MemoryItem.model_validate(raw)
                except ValidationError:
                    invalid += 1
                    logger.warning("Skipping invalid LTM record during snapshot export", exc_info=True)
                    continue

                collected.append(item.model_dump())
                if limit is not None and len(collected) >= limit:
                    break

            if limit is not None and len(collected) >= limit:
                break

            if len(items) < batch_limit:
                break

        snapshot: dict[str, Any] = {
            "version": self.VERSION,
            "tier": self._tier_name,
            "exported_at": self._clock().isoformat(),
            "filters": filters or {},
            "count": len(collected),
            "invalid": invalid,
            "memories": collected,
        }
        if total_count is not None:
            snapshot["total"] = total_count

        if self._lifecycle is not None:
            categories = self._serialize_categories(self._lifecycle.get_category_map())
            relationships = self._serialize_relationships(self._lifecycle.get_relationship_map())
            if categories:
                snapshot["categories"] = categories
            if relationships:
                snapshot["relationships"] = relationships

        return snapshot

    async def restore_snapshot(
        self,
        snapshot: Mapping[str, Any],
        *,
        overwrite: bool = False,
    ) -> dict[str, int]:
        """Restore memories from a redundancy snapshot."""

        backend = self._require_backend()

        if not isinstance(snapshot, Mapping):
            raise ValueError("LTM snapshot must be a mapping")

        snapshot_tier = snapshot.get("tier")
        if snapshot_tier and snapshot_tier != self._tier_name:
            raise ValueError(
                f"Snapshot tier {snapshot_tier!r} does not match {self._tier_name!r}"
            )

        raw_memories = snapshot.get("memories", [])
        if not isinstance(raw_memories, list):
            raise ValueError("Snapshot 'memories' section must be a list")

        restored = created = updated = skipped = invalid = 0

        for raw in raw_memories:
            try:
                item = MemoryItem.model_validate(raw)
            except ValidationError:
                invalid += 1
                logger.warning("Skipping invalid LTM record during snapshot restore", exc_info=True)
                continue

            payload = item.model_dump()
            exists = await backend.exists(item.id)

            if exists:
                if overwrite:
                    await backend.update(item.id, payload)
                    restored += 1
                    updated += 1
                else:
                    skipped += 1
                continue

            await backend.create(item.id, payload)
            restored += 1
            created += 1

        if self._lifecycle is not None:
            categories = self._coerce_categories(snapshot.get("categories"))
            relationships = self._coerce_relationships(snapshot.get("relationships"))
            self._lifecycle.apply_snapshot_state(
                categories=categories,
                relationships=relationships,
            )

        return {
            "restored": restored,
            "created": created,
            "updated": updated,
            "skipped": skipped,
            "invalid": invalid,
        }

    def _require_backend(self) -> BaseStorageBackend:
        if self._backend is None:
            raise RuntimeError("LTMSnapshotExporter requires a configured backend")
        return self._backend

    def _resolve_batch_size(self, override: int | None) -> int:
        size = override if override is not None and override > 0 else self._batch_size
        return max(1, size)

    def _build_filters(
        self, statuses: Iterable[MemoryStatus | str] | None
    ) -> dict[str, Any]:
        if statuses is None:
            statuses = self.DEFAULT_STATUSES

        normalized: list[str] = []
        for status in statuses:
            if isinstance(status, MemoryStatus):
                normalized.append(status.value)
            elif isinstance(status, str) and status:
                normalized.append(status)

        if not normalized:
            return {}

        return {"metadata.status": {"$in": normalized}}

    @staticmethod
    def _serialize_categories(categories: Mapping[str, Iterable[str]]) -> dict[str, list[str]]:
        serialized: dict[str, list[str]] = {}
        for category, memory_ids in categories.items():
            if category is None:
                continue
            ids = [str(memory_id) for memory_id in memory_ids if memory_id]
            if ids:
                serialized[str(category)] = sorted(set(ids))
        return serialized

    @staticmethod
    def _serialize_relationships(
        relationships: Mapping[str, Mapping[str, float]]
    ) -> dict[str, dict[str, float]]:
        serialized: dict[str, dict[str, float]] = {}
        for memory_id, related in relationships.items():
            if memory_id is None:
                continue
            related_map: dict[str, float] = {}
            for related_id, strength in related.items():
                if related_id is None:
                    continue
                try:
                    value = float(strength)
                except (TypeError, ValueError):
                    continue
                if not (0.0 <= value <= 1.0):
                    value = max(0.0, min(1.0, value))
                related_map[str(related_id)] = value
            if related_map:
                serialized[str(memory_id)] = related_map
        return serialized

    @staticmethod
    def _coerce_categories(value: Any) -> dict[str, list[str]]:
        if not isinstance(value, Mapping):
            return {}
        coerced: dict[str, list[str]] = {}
        for category, memory_ids in value.items():
            if category is None:
                continue
            ids: list[str] = []
            if isinstance(memory_ids, Mapping):
                iterator = memory_ids.keys()
            else:
                iterator = memory_ids
            for memory_id in iterator:
                if memory_id:
                    ids.append(str(memory_id))
            if ids:
                coerced[str(category)] = ids
        return coerced

    @staticmethod
    def _coerce_relationships(value: Any) -> dict[str, dict[str, float]]:
        if not isinstance(value, Mapping):
            return {}
        coerced: dict[str, dict[str, float]] = {}
        for memory_id, related in value.items():
            if memory_id is None or not isinstance(related, Mapping):
                continue
            related_map: dict[str, float] = {}
            for related_id, strength in related.items():
                if related_id is None:
                    continue
                try:
                    value_float = float(strength)
                except (TypeError, ValueError):
                    continue
                value_float = max(0.0, min(1.0, value_float))
                related_map[str(related_id)] = value_float
            if related_map:
                coerced[str(memory_id)] = related_map
        return coerced
