"""Regression tests for the v1 memory API contract."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from neuroca.api.contracts.memory_v1 import (
    MemoryCreateRequestV1,
    MemoryMetadataPayloadV1,
    MemoryRecordV1,
)
from neuroca.api.routes import memory_v1
from neuroca.api.routes.memory import router as memory_router
from neuroca.api.routes.memory_v1 import _ensure_access, _to_memory_record
from neuroca.core.exceptions import MemoryAccessDeniedError, MemoryStorageError
from neuroca.memory.service import MemoryResponse, MemorySearchParams


class DummyUser:
    """Minimal user returned by the authentication dependency."""
 
    def __init__(
        self,
        user_id: str = "user-1",
        *,
        is_admin: bool = False,
        session_id: str | None = None,
        tenant_id: str | None = None,
    ) -> None:
        self.id = user_id
        self.is_admin = is_admin
        self.session_id = session_id
        self.tenant_id = tenant_id
        self.roles: list[str] = []


class DummyMemoryService:
    """Test double that captures service interactions for verification."""

    def __init__(self) -> None:
        self.last_create: dict[str, Any] | None = None
        self.last_list: MemorySearchParams | None = None

    async def create_memory(self, payload: dict[str, Any]) -> MemoryResponse:
        self.last_create = payload
        return MemoryResponse(
            id="mem-123",
            user_id=payload.get("user_id"),
            tier=payload.get("tier", "stm"),
            content={"text": payload.get("content", {}).get("text", "")},
            metadata={
                "user_id": payload.get("user_id"),
                "tier": payload.get("tier", "stm"),
                "tags": {tag: True for tag in payload.get("tags", [])},
            },
        )

    async def get_memory(self, memory_id: UUID, **_: Any) -> MemoryResponse:
        return MemoryResponse(
            id=str(memory_id),
            user_id="user-1",
            tier="stm",
            content={"text": "hello"},
            metadata={"user_id": "user-1", "tier": "stm"},
        )

    async def list_memories(self, search_params: MemorySearchParams, **_: Any) -> list[MemoryResponse]:
        self.last_list = search_params
        return [
            MemoryResponse(
                id="mem-123",
                user_id="user-1",
                tier="stm",
                content={"text": "hello"},
                metadata={"user_id": "user-1", "tier": "stm", "tags": {"focus": True}},
            )
        ]

    async def update_memory(self, memory_id: UUID, *_: Any, **__: Any) -> MemoryResponse:
        return await self.get_memory(memory_id)

    async def delete_memory(self, memory_id: UUID) -> None:  # pragma: no cover - behaviour verified via status code
        return None

    async def transfer_memory(self, memory_id: UUID, target_tier: str) -> MemoryResponse:
        return MemoryResponse(
            id=str(memory_id),
            user_id="user-1",
            tier=target_tier,
            content={"text": "hello"},
            metadata={"user_id": "user-1", "tier": target_tier},
        )


@pytest.fixture()
def client_with_overrides() -> tuple[TestClient, DummyMemoryService]:
    app = FastAPI()
    app.include_router(memory_router, prefix="/api")

    service = DummyMemoryService()
    app.dependency_overrides[memory_v1.get_memory_service] = lambda: service
    app.dependency_overrides[memory_v1.authenticate_request] = lambda: DummyUser()

    client = TestClient(app)
    try:
        yield client, service
    finally:
        app.dependency_overrides.clear()


def test_memory_router_exposes_versioned_routes() -> None:
    app = FastAPI()
    app.include_router(memory_router, prefix="/api")

    paths = {route.path for route in app.routes}

    assert "/api/v1/memory" in paths
    assert "/api/v1/memory/{memory_id}" in paths
    assert "/api/v1/memory/transfer" in paths


def test_create_memory_contract_returns_structured_record(client_with_overrides: tuple[TestClient, DummyMemoryService]) -> None:
    client, service = client_with_overrides

    response = client.post(
        "/api/v1/memory",
        json={"content": "Focus on the milestone", "tags": ["focus"]},
    )

    assert response.status_code == 201
    payload = response.json()

    assert payload["id"] == "mem-123"
    assert payload["tier"] == "stm"
    assert payload["metadata"]["user_id"] == "user-1"
    assert service.last_create is not None
    assert service.last_create["content"]["text"] == "Focus on the milestone"
    assert service.last_create["user_id"] == "user-1"


def test_list_memories_uses_query_contract(client_with_overrides: tuple[TestClient, DummyMemoryService]) -> None:
    client, service = client_with_overrides

    response = client.get(
        "/api/v1/memory",
        params=[("tier", "stm"), ("limit", "5"), ("tags", "focus"), ("tags", "agent")],
    )

    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list)
    assert payload[0]["id"] == "mem-123"
    assert service.last_list is not None
    assert service.last_list.limit == 5
    assert service.last_list.tier == "stm"
    assert service.last_list.tags == ["focus", "agent"]


def test_memory_record_contract_schema_is_stable() -> None:
    schema = MemoryRecordV1.model_json_schema()

    assert set(schema["properties"].keys()) == {"id", "tier", "user_id", "content", "metadata"}
    metadata_schema = schema["$defs"]["MemoryMetadataPayloadV1"]
    metadata_props = metadata_schema["properties"]
    assert "user_id" in metadata_props
    assert "tags" in metadata_props


def test_create_request_requires_content() -> None:
    with pytest.raises(ValidationError):
        MemoryCreateRequestV1.model_validate({})


def test_to_memory_record_rejects_missing_user_identifier() -> None:
    response = MemoryResponse(
        id="mem-404",
        tier="stm",
        content={"text": "hello"},
        metadata={"tier": "stm"},
    )

    with pytest.raises(MemoryStorageError):
        _to_memory_record(response)


def test_to_memory_record_coerces_uuid_user_identifier() -> None:
    owner = UUID("12345678-1234-5678-1234-567812345678")
    response = MemoryResponse(
        id="mem-uuid",
        user_id=owner,
        tier="stm",
        content={"text": "hello"},
        metadata={"tier": "stm"},
    )
 
    record = _to_memory_record(response)
 
    assert record.user_id == str(owner)
 
 
def test_ensure_access_allows_same_tenant_and_user() -> None:
    record = MemoryRecordV1(
        id="mem-tenant-1",
        tier="stm",
        user_id="user-1",
        metadata=MemoryMetadataPayloadV1(
            user_id="user-1",
            tenant_id="tenant-a",
        ),
    )
 
    user = DummyUser(user_id="user-1", tenant_id="tenant-a")
 
    _ensure_access(record, user, operation="read")
 
 
def test_ensure_access_rejects_cross_tenant_access() -> None:
    record = MemoryRecordV1(
        id="mem-tenant-2",
        tier="stm",
        user_id="user-1",
        metadata=MemoryMetadataPayloadV1(
            user_id="user-1",
            tenant_id="tenant-a",
        ),
    )
 
    user = DummyUser(user_id="user-1", tenant_id="tenant-b")
 
    with pytest.raises(MemoryAccessDeniedError):
        _ensure_access(record, user, operation="read")
