"""
Vector Storage Backend Core

This module provides the `VectorBackend` implementation that conforms to the
`BaseStorageBackend` interface while leveraging the vector-specific CRUD,
storage, and statistics components.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from neuroca.memory.backends.base import BaseStorageBackend
from neuroca.memory.backends.vector.components.crud import VectorCRUD
from neuroca.memory.backends.vector.components.index import VectorIndex
from neuroca.memory.backends.vector.components.stats import VectorStats
from neuroca.memory.backends.vector.components.storage import VectorStorage
from neuroca.memory.exceptions import (
    StorageBackendError,
    StorageInitializationError,
    StorageOperationError,
)
from neuroca.memory.interfaces import StorageStats
from neuroca.memory.models.memory_item import MemoryItem
from neuroca.memory.models.search import (
    MemorySearchOptions,
    MemorySearchResult,
    MemorySearchResults,
)

logger = logging.getLogger(__name__)


class VectorBackend(BaseStorageBackend):
    """Vector database implementation of the storage backend interface."""

    def __init__(
        self,
        dimension: int = 768,
        similarity_threshold: float = 0.75,
        index_path: Optional[str] = None,
        **config: Any,
    ) -> None:
        base_config: Dict[str, Any] = dict(config)
        base_config.setdefault("dimension", dimension)
        base_config.setdefault("similarity_threshold", similarity_threshold)
        if index_path is not None:
            base_config.setdefault("index_path", index_path)

        super().__init__(base_config)

        self.dimension = dimension
        self.similarity_threshold = similarity_threshold
        self.index_path = index_path

        self._create_components()

    # ------------------------------------------------------------------
    # Component wiring
    # ------------------------------------------------------------------
    def _create_components(self) -> None:
        self.index = VectorIndex(dimension=self.dimension)
        self.storage = VectorStorage(index=self.index, index_path=self.index_path)
        self.crud = VectorCRUD(index=self.index, storage=self.storage)
        self.stats_component = VectorStats(index=self.index, storage=self.storage)

    # ------------------------------------------------------------------
    # BaseStorageBackend contract
    # ------------------------------------------------------------------
    async def initialize(self, config: Optional[Dict[str, Any]] = None) -> None:
        try:
            await super().initialize(config)
        except StorageInitializationError:
            raise
        except Exception as error:  # pragma: no cover - defensive rewrap
            logger.error("Unexpected error during vector backend init", exc_info=True)
            raise StorageInitializationError(str(error)) from error

    async def shutdown(self) -> None:
        try:
            await super().shutdown()
        except StorageBackendError:
            raise
        except Exception as error:  # pragma: no cover - defensive rewrap
            logger.error("Unexpected error during vector backend shutdown", exc_info=True)
            raise StorageBackendError(str(error)) from error

    async def _initialize_backend(self) -> None:
        await self.storage.initialize()

    async def _shutdown_backend(self) -> None:
        await self.storage.save()

    async def _get_backend_stats(self) -> Dict[str, Any]:
        stats: StorageStats = await self.stats_component.get_stats()
        return stats.model_dump() if hasattr(stats, "model_dump") else dict(stats)

    async def _create_item(self, item_id: str, data: Dict[str, Any]) -> bool:
        memory_item = self._coerce_memory_item(item_id, data)
        await self.crud.create(memory_item)
        return True

    async def _read_item(self, item_id: str) -> Optional[Dict[str, Any]]:
        memory_item = await self.crud.read(item_id)
        return memory_item.model_dump(mode="json") if memory_item else None

    async def _update_item(self, item_id: str, data: Dict[str, Any]) -> bool:
        memory_item = self._coerce_memory_item(item_id, data, allow_missing_embedding=True)
        return await self.crud.update(memory_item)

    async def _delete_item(self, item_id: str) -> bool:
        return await self.crud.delete(item_id)

    async def _item_exists(self, item_id: str) -> bool:
        return await self.crud.exists(item_id)

    async def _query_items(
        self,
        filters: Optional[Dict[str, Any]] = None,
        sort_by: Optional[str] = None,
        ascending: bool = True,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        matched_ids = self._filter_memory_ids(filters)
        if offset:
            matched_ids = matched_ids[offset:]
        if limit is not None:
            matched_ids = matched_ids[:limit]

        if not matched_ids:
            return []

        batch = await self.crud.batch_read(matched_ids)
        memory_dicts: List[Dict[str, Any]] = [
            batch[memory_id].model_dump(mode="json")
            for memory_id in matched_ids
            if batch.get(memory_id) is not None
        ]

        if sort_by:
            memory_dicts.sort(
                key=lambda entry: self._extract_sort_value(entry, sort_by),
                reverse=not ascending,
            )

        return memory_dicts

    async def _count_items(self, filters: Optional[Dict[str, Any]] = None) -> int:
        return len(self._filter_memory_ids(filters))

    async def _clear_all_items(self) -> bool:
        await self.storage.clear()
        return True

    async def _batch_create_items(self, items: Dict[str, Dict[str, Any]]) -> Dict[str, bool]:
        memory_items = [self._coerce_memory_item(item_id, data) for item_id, data in items.items()]
        created_ids = await self.crud.batch_create(memory_items)
        return {item_id: item_id in created_ids for item_id in items}

    async def _batch_read_items(self, item_ids: List[str]) -> Dict[str, Optional[Dict[str, Any]]]:
        batch = await self.crud.batch_read(item_ids)
        return {
            item_id: memory.model_dump(mode="json") if memory else None
            for item_id, memory in batch.items()
        }

    async def _batch_delete_items(self, item_ids: List[str]) -> Dict[str, bool]:
        return await self.crud.batch_delete(item_ids)

    # ------------------------------------------------------------------
    # Compatibility helpers expected by factory checks
    # ------------------------------------------------------------------
    async def store(self, memory_item: MemoryItem) -> str:
        await self.create(memory_item.id, memory_item.model_dump(mode="json"))
        return memory_item.id

    async def retrieve(self, memory_id: str) -> Optional[MemoryItem]:
        data = await self.read(memory_id)
        return MemoryItem.model_validate(data) if data else None

    async def update(self, memory_item: MemoryItem) -> bool:  # type: ignore[override]
        return await BaseStorageBackend.update(
            self,
            memory_item.id,
            memory_item.model_dump(mode="json"),
        )

    async def delete(self, memory_id: str) -> bool:  # type: ignore[override]
        return await BaseStorageBackend.delete(self, memory_id)

    async def batch_store(self, memory_items: List[MemoryItem]) -> List[str]:
        created = await self._batch_create_items(
            {item.id: item.model_dump(mode="json") for item in memory_items}
        )
        return [item_id for item_id, success in created.items() if success]

    async def batch_delete(self, memory_ids: List[str]) -> int:
        results = await self._batch_delete_items(memory_ids)
        return sum(1 for success in results.values() if success)

    async def exists(self, item_id: str) -> bool:  # type: ignore[override]
        return await BaseStorageBackend.exists(self, item_id)

    async def search(
        self,
        query: str,
        filter: Optional[MemorySearchOptions] = None,
        limit: int = 10,
        offset: int = 0,
        query_embedding: Optional[List[float]] = None,
    ) -> MemorySearchResults:
        if not query_embedding:
            raise StorageOperationError("Query embedding is required for vector search")

        filter_dict = filter.metadata_filters if filter else None
        results = await self.similarity_search(
            embedding=query_embedding,
            filters=filter_dict,
            limit=limit,
            offset=offset,
        )

        options = filter or MemorySearchOptions(
            query=query,
            embedding=query_embedding,
            limit=limit,
            offset=offset,
        )

        search_results = [
            MemorySearchResult(
                memory=MemoryItem.model_validate(entry),
                relevance=entry.get("metadata", {}).get("relevance", 1.0),
                tier=entry.get("metadata", {}).get("tier", "ltm") or "ltm",
                rank=index + 1,
                similarity=entry.get("metadata", {}).get("relevance"),
            )
            for index, entry in enumerate(results)
        ]

        return MemorySearchResults(
            results=search_results,
            total_count=len(self._filter_memory_ids(filter_dict)),
            query=query,
            options=options,
        )

    async def count(self, filter: Optional[MemorySearchOptions] = None) -> int:
        return await self._count_items(filter.metadata_filters if filter else None)

    async def get_stats(self) -> StorageStats:  # type: ignore[override]
        return await self.stats_component.get_stats()

    async def similarity_search(
        self,
        embedding: List[float],
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 10,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        if not embedding:
            raise StorageOperationError("Embedding must be provided for vector search")

        fetch = max(limit + offset, limit)
        raw_results = self.index.search(
            query_vector=embedding,
            k=fetch + 50,
            similarity_threshold=self.similarity_threshold,
        )

        candidate_ids: List[str] = []
        similarity_map: Dict[str, float] = {}

        for memory_id, similarity in raw_results:
            metadata = self.storage.get_memory_metadata(memory_id)
            memory_payload = metadata.get("memory")
            if not memory_payload:
                entry = self.index.get(memory_id)
                if entry is None:
                    continue
                memory_payload = self.crud._vector_entry_to_memory(entry, metadata).model_dump(mode="json")
                metadata["memory"] = memory_payload
                self.storage.set_memory_metadata(memory_id, metadata)

            if filters and not self._matches_filters(memory_payload, filters):
                continue

            candidate_ids.append(memory_id)
            similarity_map[memory_id] = similarity

        if offset:
            candidate_ids = candidate_ids[offset:]
        if limit:
            candidate_ids = candidate_ids[:limit]

        batch = await self.crud.batch_read(candidate_ids)
        results: List[Dict[str, Any]] = []

        for memory_id in candidate_ids:
            memory_item = batch.get(memory_id)
            if not memory_item:
                continue

            memory_item.metadata.relevance = similarity_map.get(memory_id)
            memory_dict = memory_item.model_dump(mode="json")
            results.append(memory_dict)

        return results

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _coerce_memory_item(
        self,
        item_id: str,
        data: Dict[str, Any],
        *,
        allow_missing_embedding: bool = False,
    ) -> MemoryItem:
        memory_item = MemoryItem.model_validate(data)
        if item_id:
            memory_item.id = item_id

        if not memory_item.embedding:
            if allow_missing_embedding:
                existing_entry = self.index.get(memory_item.id)
                if existing_entry is None:
                    raise StorageOperationError(
                        "Existing memory does not contain an embedding"
                    )
                memory_item.embedding = existing_entry.vector
            else:
                raise StorageOperationError(
                    "Vector backend requires an embedding on stored memory items"
                )

        return memory_item

    def _filter_memory_ids(self, filters: Optional[Dict[str, Any]]) -> List[str]:
        if not filters:
            return list(self.storage.get_all_memory_metadata().keys())

        matched: List[str] = []
        for memory_id, metadata in self.storage.get_all_memory_metadata().items():
            memory_payload = metadata.get("memory")
            if memory_payload and self._matches_filters(memory_payload, filters):
                matched.append(memory_id)

        return matched

    def _matches_filters(self, memory_payload: Dict[str, Any], filters: Dict[str, Any]) -> bool:
        for key, expected in filters.items():
            actual = self._extract_nested_value(memory_payload, key)

            if isinstance(expected, dict):
                if "$exists" in expected:
                    exists = actual is not None
                    if bool(expected["$exists"]) != exists:
                        return False
                elif "$in" in expected:
                    if actual not in expected["$in"]:
                        return False
                else:
                    continue
            else:
                if isinstance(actual, list) and not isinstance(expected, list):
                    if expected not in actual:
                        return False
                elif actual != expected:
                    return False

        return True

    @staticmethod
    def _extract_nested_value(payload: Dict[str, Any], dotted_key: str) -> Any:
        current: Any = payload
        for part in dotted_key.split("."):
            if isinstance(current, dict):
                current = current.get(part)
            else:
                return None
        return current

    def _extract_sort_value(self, payload: Dict[str, Any], sort_key: str) -> Any:
        value = self._extract_nested_value(payload, sort_key)
        return value if value is not None else 0
