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

        total_count = await self._safe_count(backend, filters)
        memories, invalid = await self._collect_memories(
            backend=backend,
            filters=filters,
            limit=limit,
            batch_size=requested_batch,
        )

        snapshot = self._assemble_snapshot(filters, memories, invalid, total_count)
        self._include_lifecycle_state(snapshot)
        return snapshot

    async def restore_snapshot(
        self,
        snapshot: Mapping[str, Any],
        *,
        overwrite: bool = False,
    ) -> dict[str, int]:
        """Restore memories from a redundancy snapshot."""

        backend = self._require_backend()

        raw_memories, categories, relationships = self._normalize_snapshot(snapshot)
        results = await self._apply_memories(backend, raw_memories, overwrite)
        self._restore_lifecycle_state(categories, relationships)
        return results

    async def _safe_count(
        self,
        backend: BaseStorageBackend,
        filters: Mapping[str, Any] | None,
    ) -> int | None:
        try:
            return await backend.count(filters or None)
        except Exception:  # pragma: no cover - defensive logging path
            logger.warning("Failed to count LTM records before export", exc_info=True)
            return None

    async def _collect_memories(
        self,
        *,
        backend: BaseStorageBackend,
        filters: Mapping[str, Any] | None,
        limit: int | None,
        batch_size: int,
    ) -> tuple[list[dict[str, Any]], int]:
        collected: list[dict[str, Any]] = []
        invalid = 0
        offset = 0

        while self._has_capacity(limit, len(collected)):
            batch_limit = self._calculate_batch_limit(batch_size, limit, len(collected))
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
            processed, batch_invalid, should_continue = self._process_batch(
                items, limit, len(collected)
            )
            collected.extend(processed)
            invalid += batch_invalid

            if not should_continue or len(items) < batch_limit:
                break

        return collected, invalid

    def _assemble_snapshot(
        self,
        filters: Mapping[str, Any] | None,
        memories: list[dict[str, Any]],
        invalid: int,
        total_count: int | None,
    ) -> dict[str, Any]:
        snapshot: dict[str, Any] = {
            "version": self.VERSION,
            "tier": self._tier_name,
            "exported_at": self._clock().isoformat(),
            "filters": filters or {},
            "count": len(memories),
            "invalid": invalid,
            "memories": memories,
        }
        if total_count is not None:
            snapshot["total"] = total_count
        return snapshot

    def _include_lifecycle_state(self, snapshot: dict[str, Any]) -> None:
        if self._lifecycle is None:
            return
        categories = self._serialize_categories(self._lifecycle.get_category_map())
        relationships = self._serialize_relationships(
            self._lifecycle.get_relationship_map()
        )
        if categories:
            snapshot["categories"] = categories
        if relationships:
            snapshot["relationships"] = relationships

    def _normalize_snapshot(
        self, snapshot: Mapping[str, Any]
    ) -> tuple[list[Any], Any, Any]:
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

        return raw_memories, snapshot.get("categories"), snapshot.get("relationships")

    async def _apply_memories(
        self,
        backend: BaseStorageBackend,
        raw_memories: Sequence[Any],
        overwrite: bool,
    ) -> dict[str, int]:
        restored = created = updated = skipped = invalid = 0

        for raw in raw_memories:
            item = self._parse_memory_item(raw, context="restore")
            if item is None:
                invalid += 1
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

        return {
            "restored": restored,
            "created": created,
            "updated": updated,
            "skipped": skipped,
            "invalid": invalid,
        }

    def _restore_lifecycle_state(self, categories: Any, relationships: Any) -> None:
        if self._lifecycle is None:
            return
        self._lifecycle.apply_snapshot_state(
            categories=self._coerce_categories(categories),
            relationships=self._coerce_relationships(relationships),
        )

    def _parse_memory_item(
        self, raw: Any, *, context: str
    ) -> MemoryItem | None:
        try:
            return MemoryItem.model_validate(raw)
        except ValidationError:
            logger.warning(
                "Skipping invalid LTM record during snapshot %s", context, exc_info=True
            )
            return None

    @staticmethod
    def _has_capacity(limit: int | None, count: int) -> bool:
        return limit is None or count < limit

    @staticmethod
    def _calculate_batch_limit(
        batch_size: int, limit: int | None, collected: int
    ) -> int:
        if limit is None:
            return batch_size
        remaining = limit - collected
        return batch_size if remaining >= batch_size else max(1, remaining)

    def _process_batch(
        self,
        items: Sequence[Any],
        limit: int | None,
        collected_count: int,
    ) -> tuple[list[dict[str, Any]], int, bool]:
        processed: list[dict[str, Any]] = []
        invalid = 0
        remaining = None if limit is None else max(0, limit - collected_count)

        for raw in items:
            if remaining == 0:
                break

            item = self._parse_memory_item(raw, context="export")
            if item is None:
                invalid += 1
                continue

            processed.append(item.model_dump())
            if remaining is not None:
                remaining -= 1

        should_continue = remaining is None or remaining > 0
        return processed, invalid, should_continue

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
            if memory_id is None:
                continue
            normalized = LTMSnapshotExporter._normalize_relationship_entries(related)
            if normalized:
                coerced[str(memory_id)] = normalized
        return coerced

    @staticmethod
    def _normalize_relationship_entries(value: Any) -> dict[str, float]:
        if not isinstance(value, Mapping):
            return {}
        normalized: dict[str, float] = {}
        for related_id, strength in value.items():
            if related_id is None:
                continue
            value_float = LTMSnapshotExporter._coerce_relationship_strength(strength)
            if value_float is not None:
                normalized[str(related_id)] = value_float
        return normalized

    @staticmethod
    def _coerce_relationship_strength(strength: Any) -> float | None:
        try:
            value = float(strength)
        except (TypeError, ValueError):
            return None
        return max(0.0, min(1.0, value))
