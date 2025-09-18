from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Optional
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from neuroca.api.routes.memory import router as memory_router
from neuroca.api.routes import memory_v1
from neuroca.memory.service import MemoryResponse, MemorySearchParams
from neuroca.core.exceptions import MemoryNotFoundError


class DummyUser:
    """Lightweight user returned by the authentication dependency."""

    def __init__(self, user_id: str = "user-1", *, is_admin: bool = True) -> None:
        self.id = user_id
        self.is_admin = is_admin
        self.session_id: Optional[str] = None
        self.roles: List[str] = []


def _merge_tags(*maps: Mapping[str, Any] | Iterable[str] | None) -> Dict[str, Any]:
    """Merge tag payloads into a canonical mapping."""

    merged: Dict[str, Any] = {}
    for payload in maps:
        if payload is None:
            continue
        if isinstance(payload, Mapping):
            for key, value in payload.items():
                merged[str(key)] = value if isinstance(value, bool) else value or True
        else:
            for tag in payload:
                merged[str(tag)] = True
    return merged


class StubMemoryManager:
    """In-memory MemoryManager test double used by the smoke test."""

    def __init__(self) -> None:
        self._tiers: Dict[str, Dict[str, Dict[str, Any]]] = {
            "stm": {},
            "mtm": {},
            "ltm": {},
        }

    async def initialize(self) -> None:  # pragma: no cover - no-op for compatibility
        return None

    async def shutdown(self) -> None:  # pragma: no cover - no-op for compatibility
        self._tiers = {"stm": {}, "mtm": {}, "ltm": {}}

    async def add_memory(
        self,
        content: Mapping[str, Any] | str,
        summary: Optional[str] = None,
        importance: float = 0.5,
        metadata: Optional[MutableMapping[str, Any]] = None,
        tags: Optional[Iterable[str]] = None,
        embedding: Optional[List[float]] = None,
        initial_tier: Optional[str] = None,
    ) -> str:
        del embedding  # Embeddings are not required for the smoke test.
        tier = (initial_tier or "stm").lower()
        memory_id = str(uuid4())

        if isinstance(content, str):
            text = content
            json_payload: Optional[Dict[str, Any]] = None
        else:
            text = content.get("text")
            json_payload = {key: value for key, value in content.items() if key != "text"}

        metadata_dict: Dict[str, Any] = dict(metadata or {})
        metadata_dict.setdefault("user_id", metadata_dict.get("user_id"))
        metadata_dict.setdefault("importance", importance)
        metadata_dict.setdefault("strength", 1.0)
        metadata_dict.setdefault("access_count", metadata_dict.get("access_count", 0))
        metadata_dict["tier"] = tier
        metadata_dict["tags"] = _merge_tags(metadata_dict.get("tags"), tags)

        record = {
            "id": memory_id,
            "tier": tier,
            "content": {
                "text": text,
                "summary": summary,
                "json_data": None if text is not None else json_payload,
                "raw_content": None,
            },
            "metadata": metadata_dict,
        }
        self._tiers[tier][memory_id] = record
        return memory_id

    async def retrieve_memory(
        self,
        memory_id: str,
        tier: Optional[str] = None,
        scope: Any | None = None,
    ) -> Optional[Dict[str, Any]]:
        del scope
        tiers = [tier.lower()] if tier else ["stm", "mtm", "ltm"]
        for name in tiers:
            record = self._tiers.get(name, {}).get(memory_id)
            if record:
                return record
        return None

    async def search_memories(
        self,
        query: Optional[str] = None,
        embedding: Optional[List[float]] = None,
        tags: Optional[List[str]] = None,
        metadata_filters: Optional[Mapping[str, Any]] = None,
        limit: int = 10,
        min_relevance: float = 0.0,
        tiers: Optional[List[str]] = None,
        scope: Any | None = None,
    ) -> List[Dict[str, Any]]:
        del embedding, min_relevance, scope
        tag_filters = set(tags or [])
        tier_names = [name.lower() for name in tiers] if tiers else ["stm", "mtm", "ltm"]
        results: List[Dict[str, Any]] = []
        for tier in tier_names:
            for record in self._tiers.get(tier, {}).values():
                if metadata_filters:
                    user_filter = metadata_filters.get("metadata.user_id")
                    if user_filter is not None and record["metadata"].get("user_id") != user_filter:
                        continue
                if tag_filters:
                    stored_tags = record["metadata"].get("tags", {})
                    if not tag_filters.issubset(stored_tags.keys()):
                        continue
                if query:
                    text = (record["content"].get("text") or "").lower()
                    summary = (record["content"].get("summary") or "").lower()
                    if query.lower() not in text and query.lower() not in summary:
                        continue
                enriched = dict(record)
                enriched["tier"] = tier
                results.append(enriched)
        return results[:limit]

    async def update_memory(
        self,
        memory_id: str,
        content: Optional[Mapping[str, Any]] = None,
        summary: Optional[str] = None,
        importance: Optional[float] = None,
        metadata: Optional[Mapping[str, Any]] = None,
        tags: Optional[Iterable[str]] = None,
    ) -> bool:
        tier, record = self._locate(memory_id)
        if record is None:
            return False

        if content:
            record["content"]["text"] = content.get("text")
            json_payload = {key: value for key, value in content.items() if key != "text"}
            record["content"]["json_data"] = None if json_payload == {} else json_payload
        if summary is not None:
            record["content"]["summary"] = summary
        if importance is not None:
            record["metadata"]["importance"] = importance
        if metadata:
            for key, value in metadata.items():
                if key == "tags" and isinstance(value, Mapping):
                    record["metadata"]["tags"].update(value)
                else:
                    record["metadata"][key] = value
        if tags is not None:
            record["metadata"]["tags"].update({tag: True for tag in tags})

        self._tiers[tier][memory_id] = record
        return True

    async def delete_memory(self, memory_id: str, tier: Optional[str] = None) -> bool:
        tiers = [tier.lower()] if tier else ["stm", "mtm", "ltm"]
        for name in tiers:
            if memory_id in self._tiers.get(name, {}):
                del self._tiers[name][memory_id]
                return True
        return False

    async def transfer_memory(
        self,
        memory_id: str,
        target_tier: str,
    ) -> Dict[str, Any]:
        source_tier, record = self._locate(memory_id)
        if record is None:
            raise MemoryNotFoundError(f"Memory {memory_id} not found")

        resolved = str(target_tier).lower()
        if source_tier == resolved:
            return record

        del self._tiers[source_tier][memory_id]
        record["tier"] = resolved
        record["metadata"]["tier"] = resolved
        record["metadata"].setdefault("tags", {})
        self._tiers[resolved][memory_id] = record
        return record

    async def decay_memory(
        self,
        memory_id: str,
        tier: Optional[str] = None,
        decay_amount: float = 0.1,
    ) -> bool:
        _, record = self._locate(memory_id, preferred_tier=tier)
        if record is None:
            return False

        current = float(record["metadata"].get("strength", 1.0))
        record["metadata"]["strength"] = max(0.0, current - decay_amount)
        return True

    async def promote_to_mtm(self, memory_id: str) -> None:
        record = await self.transfer_memory(memory_id, "mtm")
        record["metadata"].setdefault("tags", {})
        record["metadata"]["tags"]["promote_to_ltm"] = True

    async def promote_to_ltm(self, memory_id: str) -> None:
        record = await self.transfer_memory(memory_id, "ltm")
        text = record["content"].get("text") or ""
        if not record["content"].get("summary"):
            record["content"]["summary"] = text[:120]
        record["metadata"]["tags"].pop("promote_to_ltm", None)

    def _locate(
        self,
        memory_id: str,
        *,
        preferred_tier: Optional[str] = None,
    ) -> tuple[str, Optional[Dict[str, Any]]]:
        tiers = [preferred_tier.lower()] if preferred_tier else ["stm", "mtm", "ltm"]
        for name in tiers:
            record = self._tiers.get(name, {}).get(memory_id)
            if record:
                return name, record
        return "stm", None


class InMemoryMemoryService:
    """Service facade backed by :class:`StubMemoryManager`."""

    def __init__(self, manager: StubMemoryManager) -> None:
        self.memory_manager = manager

    async def create_memory(self, payload: Dict[str, Any]) -> MemoryResponse:
        metadata = dict(payload.get("metadata") or {})
        metadata.setdefault("user_id", payload.get("user_id"))
        memory_id = await self.memory_manager.add_memory(
            content=payload.get("content", {}),
            summary=payload.get("summary"),
            importance=payload.get("importance", 0.5),
            metadata=metadata,
            tags=payload.get("tags"),
            initial_tier=payload.get("tier"),
        )
        stored = await self.memory_manager.retrieve_memory(memory_id)
        return MemoryResponse.from_orm(stored)

    async def get_memory(
        self,
        memory_id: UUID,
        *,
        user: Any | None = None,
        user_id: Any | None = None,
        session_id: Any | None = None,
        roles: Iterable[str] | None = None,
        allow_admin: bool | None = None,
    ) -> MemoryResponse:
        del user, user_id, session_id, roles, allow_admin
        stored = await self.memory_manager.retrieve_memory(str(memory_id))
        if stored is None:
            raise MemoryNotFoundError(f"Memory {memory_id} not found")
        return MemoryResponse.from_orm(stored)

    async def list_memories(
        self,
        search_params: MemorySearchParams,
        *,
        user: Any | None = None,
        roles: Iterable[str] | None = None,
        allow_admin: bool | None = None,
    ) -> List[MemoryResponse]:
        del user, roles, allow_admin
        metadata_filters: Dict[str, Any] | None = None
        if search_params.user_id:
            metadata_filters = {"metadata.user_id": search_params.user_id}
        tiers = [search_params.tier] if search_params.tier else None
        records = await self.memory_manager.search_memories(
            query=search_params.query,
            metadata_filters=metadata_filters,
            tiers=tiers,
            limit=search_params.limit,
        )
        return [MemoryResponse.from_orm(record) for record in records]

    async def update_memory(
        self,
        memory_id: UUID,
        update_data: Dict[str, Any],
        *,
        user: Any | None = None,
        user_id: Any | None = None,
        session_id: Any | None = None,
        roles: Iterable[str] | None = None,
        allow_admin: bool | None = None,
    ) -> MemoryResponse:
        del user, user_id, session_id, roles, allow_admin
        updated = await self.memory_manager.update_memory(
            str(memory_id),
            content=update_data.get("content"),
            summary=update_data.get("summary"),
            importance=update_data.get("importance"),
            metadata=update_data.get("metadata"),
            tags=update_data.get("tags"),
        )
        if not updated:
            raise MemoryNotFoundError(f"Memory {memory_id} not found for update")
        stored = await self.memory_manager.retrieve_memory(str(memory_id))
        return MemoryResponse.from_orm(stored)

    async def delete_memory(self, memory_id: UUID) -> None:
        deleted = await self.memory_manager.delete_memory(str(memory_id))
        if not deleted:
            raise MemoryNotFoundError(f"Memory {memory_id} not found for deletion")

    async def transfer_memory(self, memory_id: UUID, target_tier: str) -> MemoryResponse:
        record = await self.memory_manager.transfer_memory(str(memory_id), target_tier)
        return MemoryResponse.from_orm(record)


@pytest.fixture()
def memory_app() -> tuple[FastAPI, InMemoryMemoryService, StubMemoryManager]:
    manager = StubMemoryManager()
    service = InMemoryMemoryService(manager)
    app = FastAPI()
    app.include_router(memory_router, prefix="/api")
    app.dependency_overrides[memory_v1.get_memory_service] = lambda: service
    app.dependency_overrides[memory_v1.authenticate_request] = lambda: DummyUser()
    return app, service, manager


@pytest.mark.anyio
async def test_memory_lifecycle_flow(memory_app: tuple[FastAPI, InMemoryMemoryService, StubMemoryManager]) -> None:
    app, _, manager = memory_app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        create_response = await client.post(
            "/api/v1/memory",
            json={
                "content": {"text": "Remember to review the architecture proposal."},
                "importance": 0.9,
                "metadata": {"access_count": 12, "tags": {"workspace": True}},
                "tags": ["workspace"],
            },
        )
        assert create_response.status_code == 201
        created_payload = create_response.json()
        memory_id = created_payload["id"]
        assert created_payload["tier"] == "stm"

        await manager.promote_to_mtm(memory_id)
        await manager.promote_to_ltm(memory_id)

        list_response = await client.get("/api/v1/memory", params={"tier": "ltm"})
        assert list_response.status_code == 200
        listed = list_response.json()
        assert listed, "expected at least one LTM record"
        ltm_record = next(record for record in listed if record["id"] == memory_id)
        assert ltm_record["content"]["summary"], "summary should be populated after promotion"

        await manager.decay_memory(memory_id, tier="ltm", decay_amount=0.3)

        detail_response = await client.get(f"/api/v1/memory/{memory_id}")
        assert detail_response.status_code == 200
        detail_payload = detail_response.json()
        assert detail_payload["tier"] == "ltm"
        assert detail_payload["metadata"]["strength"] < 1.0

