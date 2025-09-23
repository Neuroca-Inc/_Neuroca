"""Qdrant-powered vector storage backend."""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any, Callable, Dict, List, Optional, Sequence, TypeVar

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from neuroca.memory.backends.base import BaseStorageBackend
from neuroca.memory.exceptions import StorageInitializationError, StorageOperationError
from neuroca.memory.interfaces.stats import StorageStats
from neuroca.memory.models.memory_item import MemoryItem

from .filtering import attach_relevance, extract_nested_value, matches_filters

logger = logging.getLogger(__name__)

_ResultT = TypeVar("_ResultT")


class QdrantVectorBackend(BaseStorageBackend):
    """Production-ready storage backend backed by a Qdrant collection."""

    def __init__(
        self,
        *,
        collection_name: str = "neuroca_memories",
        dimension: int = 768,
        distance: str = "cosine",
        recreate_collection: bool = False,
        client: Optional[QdrantClient] = None,
        **config: Any,
    ) -> None:
        """Configure the backend with collection metadata and connection details."""

        base_config: Dict[str, Any] = dict(config)
        base_config.setdefault("collection_name", collection_name)
        base_config.setdefault("dimension", dimension)
        base_config.setdefault("distance", distance)
        base_config.setdefault("recreate_collection", recreate_collection)
        super().__init__(base_config)

        self.collection_name = collection_name
        self.dimension = dimension
        self.distance = distance
        self.recreate_collection = recreate_collection
        self._client = client

    async def _initialize_backend(self) -> None:
        """Instantiate the Qdrant client and prepare the target collection."""

        if self._client is None:
            self._client = self._build_client()
        if self._client is None:
            raise StorageInitializationError("Qdrant client could not be created")
        if self.recreate_collection:
            await self._run_client(self._safe_delete_collection)
        await self._run_client(self._ensure_collection)

    async def _shutdown_backend(self) -> None:
        """Release Qdrant resources."""

        client = self._client
        if client is None:
            return
        try:
            await self._run_client(client.close)
        finally:
            self._client = None

    async def _create_item(self, item_id: str, data: Dict[str, Any]) -> bool:
        """Insert *data* into Qdrant using the provided identifier."""

        memory_item = self._coerce_memory_item(item_id, data)
        await self._upsert_points([self._memory_to_point(memory_item)])
        return True

    async def _read_item(self, item_id: str) -> Optional[Dict[str, Any]]:
        """Return the stored payload for *item_id* if it exists."""

        record = await self._retrieve_single(item_id)
        return self._record_to_payload(record) if record else None

    async def _update_item(self, item_id: str, data: Dict[str, Any]) -> bool:
        """Replace the stored payload for *item_id* with *data*."""

        payload = dict(data)
        if not payload.get("embedding"):
            record = await self._retrieve_single(item_id)
            vector = getattr(record, "vector", None) if record else None
            if vector is None:
                raise StorageOperationError("Qdrant backend requires embeddings on memory items")
            payload["embedding"] = list(vector)
        memory_item = self._coerce_memory_item(item_id, payload)
        await self._upsert_points([self._memory_to_point(memory_item)])
        return True

    async def _delete_item(self, item_id: str) -> bool:
        """Remove the memory entry with identifier *item_id*."""

        selector = qmodels.PointIdsList(points=[self._point_id(item_id)])
        result = await self._run_client(
            self._require_client().delete,
            collection_name=self.collection_name,
            points_selector=selector,
        )
        return bool(getattr(result, "status", None))

    async def _item_exists(self, item_id: str) -> bool:
        """Return True when *item_id* is present in the collection."""

        return await self._retrieve_single(item_id) is not None

    async def _query_items(
        self,
        filters: Optional[Dict[str, Any]] = None,
        sort_by: Optional[str] = None,
        ascending: bool = True,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Return payloads matching *filters* with optional ordering."""

        records = await self._scroll_collection()
        payloads: List[Dict[str, Any]] = []
        for record in records:
            payload = self._record_to_payload(record)
            if filters and not matches_filters(payload, filters):
                continue
            payloads.append(payload)

        if sort_by:
            payloads.sort(key=lambda entry: extract_nested_value(entry, sort_by), reverse=not ascending)
        if offset:
            payloads = payloads[offset:]
        if limit is not None:
            payloads = payloads[:limit]
        return payloads

    async def _count_items(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """Return the number of stored payloads satisfying *filters*."""

        if not filters:
            response = await self._run_client(
                self._require_client().count,
                collection_name=self.collection_name,
                exact=True,
            )
            return int(getattr(response, "count", 0))
        matches = await self._query_items(filters=filters)
        return len(matches)

    async def _clear_all_items(self) -> bool:
        """Delete and recreate the configured collection."""

        await self._run_client(self._safe_delete_collection)
        await self._run_client(self._ensure_collection)
        return True

    async def _batch_create_items(self, items: Dict[str, Dict[str, Any]]) -> Dict[str, bool]:
        """Insert *items* in a single Qdrant upsert operation."""

        points = [self._memory_to_point(self._coerce_memory_item(item_id, data)) for item_id, data in items.items()]
        await self._upsert_points(points)
        return {item_id: True for item_id in items}

    async def _batch_read_items(self, item_ids: List[str]) -> Dict[str, Optional[Dict[str, Any]]]:
        """Return payloads for all requested *item_ids*."""

        records = await self._run_client(
            self._require_client().retrieve,
            collection_name=self.collection_name,
            ids=[self._point_id(item_id) for item_id in item_ids],
            with_payload=True,
            with_vectors=True,
        )
        mapped: Dict[str, Optional[Dict[str, Any]]] = {str(item_id): None for item_id in item_ids}
        for record in records or []:
            payload = self._record_to_payload(record)
            key = str(payload.get("id", record.id))
            if key in mapped:
                mapped[key] = payload
        return mapped

    async def _batch_delete_items(self, item_ids: List[str]) -> Dict[str, bool]:
        """Remove multiple *item_ids* from the collection."""

        selector = qmodels.PointIdsList(points=[self._point_id(item_id) for item_id in item_ids])
        await self._run_client(
            self._require_client().delete,
            collection_name=self.collection_name,
            points_selector=selector,
        )
        return {item_id: True for item_id in item_ids}

    async def _get_backend_stats(self) -> Dict[str, Any]:
        """Return lightweight statistics about the underlying collection."""

        count = await self._run_client(
            self._require_client().count,
            collection_name=self.collection_name,
            exact=True,
        )
        stats = StorageStats(
            backend_type="qdrant",
            item_count=int(getattr(count, "count", 0)),
            storage_size_bytes=0,
            metadata_size_bytes=0,
            additional_info={
                "collection_name": self.collection_name,
                "vector_dimension": self.dimension,
                "distance": self.distance,
            },
        )
        return stats.to_dict()

    async def similarity_search(
        self,
        *,
        embedding: Sequence[float],
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 10,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Return the best matches for *embedding* applying optional *filters*."""

        if not embedding:
            raise StorageOperationError("Embedding must be provided for Qdrant search")

        fetch = limit + offset
        response = await self._run_client(
            self._require_client().query_points,
            collection_name=self.collection_name,
            query=list(embedding),
            limit=max(fetch, limit),
            with_payload=True,
            with_vectors=True,
        )
        points = getattr(response, "points", response) or []

        payloads: List[Dict[str, Any]] = []
        for point in points:
            payload = self._record_to_payload(point)
            if filters and not matches_filters(payload, filters):
                continue
            metadata = payload.setdefault("metadata", {})
            attach_relevance(metadata, getattr(point, "score", None))
            payloads.append(payload)

        if offset:
            payloads = payloads[offset:]
        if limit:
            payloads = payloads[:limit]
        return payloads

    async def store(self, memory_item: MemoryItem) -> str:
        """Persist *memory_item* and return its identifier."""

        await self.create(memory_item.id, memory_item.model_dump(mode="json"))
        return memory_item.id

    async def retrieve(self, memory_id: str) -> Optional[MemoryItem]:
        """Return a `MemoryItem` for *memory_id* if it exists."""

        data = await self.read(memory_id)
        return MemoryItem.model_validate(data) if data else None

    async def update(self, memory_item: MemoryItem) -> bool:  # type: ignore[override]
        """Update *memory_item* in-place within the Qdrant collection."""

        return await BaseStorageBackend.update(
            self,
            memory_item.id,
            memory_item.model_dump(mode="json"),
        )

    async def delete(self, memory_id: str) -> bool:  # type: ignore[override]
        """Delete the memory entry identified by *memory_id*."""

        return await BaseStorageBackend.delete(self, memory_id)

    async def batch_store(self, memory_items: List[MemoryItem]) -> List[str]:
        """Store *memory_items* and return the identifiers that were created."""

        created = await self._batch_create_items({item.id: item.model_dump(mode="json") for item in memory_items})
        return [item_id for item_id, success in created.items() if success]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _point_id(self, memory_id: str) -> str:
        """Return a deterministic UUID for the provided memory identifier."""

        return str(uuid.uuid5(uuid.NAMESPACE_URL, memory_id))

    def _build_client(self) -> Optional[QdrantClient]:
        """Create a Qdrant client from the stored configuration."""

        options = {
            "url": self.config.get("url"),
            "host": self.config.get("host"),
            "port": self.config.get("port"),
            "grpc_port": self.config.get("grpc_port"),
            "api_key": self.config.get("api_key"),
            "prefer_grpc": self.config.get("prefer_grpc"),
            "timeout": self.config.get("timeout"),
            "path": self.config.get("path"),
            "location": self.config.get("location"),
        }
        filtered = {key: value for key, value in options.items() if value is not None}
        if not filtered:
            filtered["location"] = ":memory:"
        return QdrantClient(**filtered)

    def _require_client(self) -> QdrantClient:
        """Return the active client or raise if initialization never happened."""

        if self._client is None:
            raise StorageInitializationError("Qdrant client not initialised")
        return self._client

    async def _run_client(self, func: Callable[..., _ResultT], *args: Any, **kwargs: Any) -> _ResultT:
        """Execute *func* in a worker thread to avoid blocking the loop."""

        return await asyncio.to_thread(func, *args, **kwargs)

    async def _retrieve_single(self, item_id: str):  # type: ignore[no-untyped-def]
        """Fetch a single record by *item_id* returning None when absent."""

        records = await self._run_client(
            self._require_client().retrieve,
            collection_name=self.collection_name,
            ids=[self._point_id(item_id)],
            with_payload=True,
            with_vectors=True,
        )
        if not records:
            return None
        return records[0]

    async def _scroll_collection(self) -> List[Any]:  # type: ignore[no-untyped-def]
        """Yield the complete set of collection records."""

        offset = None
        records: List[Any] = []
        while True:
            batch, offset = await self._run_client(
                self._require_client().scroll,
                collection_name=self.collection_name,
                limit=256,
                with_payload=True,
                with_vectors=True,
                offset=offset,
            )
            records.extend(batch or [])
            if offset is None:
                break
        return records

    async def _upsert_points(self, points: Sequence[qmodels.PointStruct]) -> None:
        """Persist *points* inside the configured collection."""

        if not points:
            return
        await self._run_client(
            self._require_client().upsert,
            collection_name=self.collection_name,
            points=list(points),
        )

    def _memory_to_point(self, memory_item: MemoryItem) -> qmodels.PointStruct:
        """Convert a `MemoryItem` into a Qdrant point structure."""

        if not memory_item.embedding:
            raise StorageOperationError("Qdrant backend requires embeddings on memory items")
        if len(memory_item.embedding) != self.dimension:
            raise StorageOperationError(
                "Embedding dimension mismatch: expected "
                f"{self.dimension}, received {len(memory_item.embedding)}"
            )
        payload = self._build_payload(memory_item)
        return qmodels.PointStruct(
            id=self._point_id(memory_item.id),
            vector=list(memory_item.embedding),
            payload=payload,
        )

    def _build_payload(self, memory_item: MemoryItem) -> Dict[str, Any]:
        """Return a serialisable payload for the provided memory item."""

        payload = memory_item.model_dump(mode="json")
        metadata = payload.get("metadata", {})
        metadata.setdefault("tier", memory_item.metadata.tier)
        payload["metadata"] = metadata
        return payload

    def _record_to_payload(self, record: Any) -> Dict[str, Any]:  # type: ignore[no-untyped-def]
        """Transform a Qdrant record into a plain dictionary payload."""

        payload = dict(getattr(record, "payload", {}) or {})
        if "embedding" not in payload and getattr(record, "vector", None) is not None:
            payload["embedding"] = list(record.vector)
        if "id" not in payload:
            payload["id"] = str(getattr(record, "id", ""))
        return payload

    def _safe_delete_collection(self) -> None:
        """Drop the collection when it already exists."""

        try:
            client = self._require_client()
            if client.collection_exists(self.collection_name):
                client.delete_collection(self.collection_name)
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.warning("Failed to drop collection %s: %s", self.collection_name, exc)

    def _ensure_collection(self) -> None:
        """Create the collection when it is missing."""

        client = self._require_client()
        if client.collection_exists(self.collection_name):
            return
        distance_map = {
            "cosine": qmodels.Distance.COSINE,
            "dot": qmodels.Distance.DOT,
            "manhattan": qmodels.Distance.MANHATTAN,
            "euclid": qmodels.Distance.EUCLID,
        }
        distance = distance_map.get(self.distance.lower(), qmodels.Distance.COSINE)
        vector_params = qmodels.VectorParams(size=self.dimension, distance=distance)
        client.create_collection(collection_name=self.collection_name, vectors_config=vector_params)

    def _coerce_memory_item(self, item_id: str, data: Dict[str, Any]) -> MemoryItem:
        """Return a validated `MemoryItem` for *data* and *item_id*."""

        memory_item = MemoryItem.model_validate(data)
        memory_item.id = item_id or memory_item.id
        if not memory_item.embedding:
            raise StorageOperationError("Qdrant backend requires embeddings on memory items")
        return memory_item
