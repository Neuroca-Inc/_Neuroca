"""Version 1 memory API contract models."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class MemoryContentPayloadV1(BaseModel):
    """Serializable representation of memory content returned by the API."""

    text: Optional[str] = Field(
        default=None,
        description="Primary textual content of the memory entry.",
    )
    summary: Optional[str] = Field(
        default=None,
        description="Optional summary derived from the memory content.",
    )
    json_data: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Structured JSON payload associated with the memory.",
    )
    raw_content: Optional[Any] = Field(
        default=None,
        description="Unstructured payload preserved as-is for downstream consumers.",
    )
    content_type: Optional[str] = Field(
        default=None,
        description="Content type hint (e.g. text/plain, application/json).",
    )
    language: Optional[str] = Field(
        default=None,
        description="BCP-47 language tag for textual payloads.",
    )

    model_config = ConfigDict(extra="allow")

    def to_service_payload(self) -> Dict[str, Any]:
        """Map the content payload to the structure expected by the service layer."""

        payload = self.model_dump(exclude_none=True)
        return dict(payload)


class MemoryMetadataPayloadV1(BaseModel):
    """Metadata envelope returned for each memory record."""

    created_at: Optional[datetime] = Field(default=None)
    last_accessed: Optional[datetime] = Field(default=None)
    updated_at: Optional[datetime] = Field(default=None)
    status: Optional[str] = Field(default=None)
    importance: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    strength: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    access_count: Optional[int] = Field(default=None, ge=0)
    user_id: Optional[str] = Field(default=None)
    session_id: Optional[str] = Field(default=None)
    tenant_id: Optional[str] = Field(default=None)
    shared_with: List[str] = Field(default_factory=list)
    tags: Dict[str, Any] = Field(default_factory=dict)
    source: Optional[str] = Field(default=None)
    tier: Optional[str] = Field(default=None)
    expires_at: Optional[datetime] = Field(default=None)
    priority: Optional[str | int] = Field(default=None)
    consolidated_from: Optional[str] = Field(default=None)
    consolidated_at: Optional[datetime] = Field(default=None)
    embedding_model: Optional[str] = Field(default=None)
    embedding_dimensions: Optional[int] = Field(default=None)
    relevance: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    additional_metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="allow")


class MemoryRecordV1(BaseModel):
    """Stable response contract for memory records returned by the API."""

    id: str = Field(..., description="Unique identifier for the memory item.")
    tier: str = Field(..., description="Resolved tier identifier (stm/mtm/ltm).")
    user_id: Optional[str] = Field(
        default=None, description="Owner of the memory item if scoped."
    )
    content: MemoryContentPayloadV1 = Field(
        default_factory=MemoryContentPayloadV1,
        description="Structured representation of the stored content.",
    )
    metadata: MemoryMetadataPayloadV1 = Field(
        default_factory=MemoryMetadataPayloadV1,
        description="Operational metadata captured for the memory entry.",
    )

    model_config = ConfigDict(extra="forbid")


class MemoryCreateRequestV1(BaseModel):
    """Body payload accepted by the create memory endpoint."""

    content: MemoryContentPayloadV1
    summary: Optional[str] = Field(
        default=None, description="Optional summary supplied by the caller."
    )
    importance: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Relative importance influencing consolidation priority.",
    )
    tags: List[str] = Field(
        default_factory=list,
        description="Flat list of tag strings applied to the memory.",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary caller metadata stored alongside the memory.",
    )
    tier: Optional[str] = Field(
        default=None, description="Preferred tier to seed the new memory into."
    )
    session_id: Optional[str] = Field(
        default=None,
        description="Session identifier used for scoping and audit trail.",
    )
    embedding: Optional[List[float]] = Field(
        default=None,
        description="Pre-computed embedding supplied by the caller (optional).",
    )

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="before")
    @classmethod
    def _coerce_content(
        cls, data: Dict[str, Any] | MemoryCreateRequestV1
    ) -> Dict[str, Any]:
        if isinstance(data, cls):  # pragma: no cover - handled by pydantic internally
            return data.model_dump()

        if "content" not in data:
            raise ValueError("content field is required")

        content = data.get("content")
        if isinstance(content, MemoryContentPayloadV1):
            return data
        if isinstance(content, str):
            data["content"] = MemoryContentPayloadV1(text=content)
            return data
        if isinstance(content, dict):
            data["content"] = MemoryContentPayloadV1(**content)
            return data

        raise TypeError("content must be a string or object with structured fields")

    def to_service_payload(
        self,
        *,
        user_id: str,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Convert the request to a dict accepted by the service layer."""

        payload = {
            "user_id": user_id,
            "content": self.content.to_service_payload(),
            "summary": self.summary,
            "importance": self.importance,
            "tags": self.tags,
            "metadata": self.metadata,
            "tier": self.tier,
            "session_id": session_id or self.session_id,
            "embedding": self.embedding,
        }
        return {key: value for key, value in payload.items() if value is not None}


class MemoryUpdateRequestV1(BaseModel):
    """Body payload for partial memory updates."""

    content: Optional[MemoryContentPayloadV1] = Field(default=None)
    summary: Optional[str] = Field(default=None)
    importance: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    metadata: Optional[Dict[str, Any]] = Field(default=None)
    tags: Optional[List[str]] = Field(default=None)

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="before")
    @classmethod
    def _coerce_optional_content(
        cls, data: Dict[str, Any] | MemoryUpdateRequestV1
    ) -> Dict[str, Any]:
        if isinstance(data, cls):  # pragma: no cover
            return data.model_dump()

        if "content" not in data or data["content"] is None:
            return data

        content = data["content"]
        if isinstance(content, MemoryContentPayloadV1):
            return data
        if isinstance(content, str):
            data["content"] = MemoryContentPayloadV1(text=content)
            return data
        if isinstance(content, dict):
            data["content"] = MemoryContentPayloadV1(**content)
            return data

        raise TypeError("content must be a string, dict, or null when updating")

    def to_service_payload(self) -> Dict[str, Any]:
        payload = self.model_dump(exclude_none=True)
        if "content" in payload:
            payload["content"] = self.content.to_service_payload()  # type: ignore[union-attr]
        return payload


class MemoryTransferRequestV1(BaseModel):
    """Body payload for transferring a memory between tiers."""

    memory_id: UUID = Field(..., description="Identifier of the memory to transfer.")
    target_tier: str = Field(..., description="Destination tier key (stm/mtm/ltm).")

    model_config = ConfigDict(extra="forbid")


class MemoryListParamsV1(BaseModel):
    """Query parameters accepted by the list endpoint."""

    query: Optional[str] = Field(default=None)
    tier: Optional[str] = Field(default=None)
    tags: List[str] = Field(default_factory=list)
    limit: int = Field(default=50, ge=1, le=100)
    offset: int = Field(default=0, ge=0)

    model_config = ConfigDict(extra="forbid")

    def with_user(self, user_id: str) -> Dict[str, Any]:
        """Return a dict suitable for instantiating MemorySearchParams."""

        return {
            "user_id": user_id,
            "query": self.query,
            "tier": self.tier,
            "tags": self.tags,
            "limit": self.limit,
            "offset": self.offset,
        }


__all__ = [
    "MemoryContentPayloadV1",
    "MemoryCreateRequestV1",
    "MemoryListParamsV1",
    "MemoryMetadataPayloadV1",
    "MemoryRecordV1",
    "MemoryTransferRequestV1",
    "MemoryUpdateRequestV1",
]
