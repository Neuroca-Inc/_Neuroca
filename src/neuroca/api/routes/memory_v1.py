"""Versioned FastAPI routes for memory operations (v1)."""

from __future__ import annotations

import logging
from typing import Any, List
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Response,
    status,
)

from neuroca.api.contracts.memory_v1 import (
    MemoryContentPayloadV1,
    MemoryCreateRequestV1,
    MemoryListParamsV1,
    MemoryMetadataPayloadV1,
    MemoryRecordV1,
    MemoryTransferRequestV1,
    MemoryUpdateRequestV1,
)
try:  # pragma: no cover - optional middleware may be unavailable in minimal envs
    from neuroca.api.middleware.authentication import authenticate_request
except ModuleNotFoundError:  # pragma: no cover
    async def authenticate_request() -> Any:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication middleware not configured",
        )
from neuroca.core.exceptions import (
    MemoryAccessDeniedError,
    MemoryNotFoundError,
    MemoryStorageError,
    MemoryTierFullError,
)
from neuroca.memory.service import (
    MemoryResponse,
    MemorySearchParams,
    MemoryService,
    User,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/v1/memory",
    tags=["memory"],
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Memory not found"},
        status.HTTP_401_UNAUTHORIZED: {"description": "Unauthorized"},
        status.HTTP_403_FORBIDDEN: {"description": "Forbidden"},
        status.HTTP_409_CONFLICT: {"description": "Tier capacity constraints"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Internal server error"},
    },
)


async def get_memory_service() -> MemoryService:
    """Dependency provider for the memory service."""

    return MemoryService()


def _normalize_content(raw: Any) -> MemoryContentPayloadV1:
    if raw is None:
        return MemoryContentPayloadV1()
    if isinstance(raw, MemoryContentPayloadV1):
        return raw
    if hasattr(raw, "model_dump"):
        raw = raw.model_dump()
    elif hasattr(raw, "dict"):
        raw = raw.dict()
    elif isinstance(raw, str):
        return MemoryContentPayloadV1(text=raw)
    elif not isinstance(raw, dict):
        raw = {"raw_content": raw}
    return MemoryContentPayloadV1(**raw)


def _normalize_metadata(raw: Any) -> MemoryMetadataPayloadV1:
    if raw is None:
        return MemoryMetadataPayloadV1()
    if isinstance(raw, MemoryMetadataPayloadV1):
        return raw
    if hasattr(raw, "model_dump"):
        payload = raw.model_dump()
    elif hasattr(raw, "dict"):
        payload = raw.dict()
    elif isinstance(raw, dict):
        payload = raw
    else:
        payload = {}
    return MemoryMetadataPayloadV1.model_validate(payload)


def _resolve_tier(raw_tier: Any, metadata: MemoryMetadataPayloadV1) -> str:
    tier_candidate = raw_tier or metadata.tier
    if hasattr(tier_candidate, "storage_key"):
        return str(getattr(tier_candidate, "storage_key"))
    if tier_candidate is None:
        return "stm"
    return str(tier_candidate)


def _to_memory_record(memory: MemoryResponse) -> MemoryRecordV1:
    metadata = _normalize_metadata(getattr(memory, "metadata", None))
    content = _normalize_content(getattr(memory, "content", None))
    raw_user_id = getattr(memory, "user_id", None)
    if raw_user_id is None:
        raw_user_id = metadata.user_id

    if raw_user_id is None:
        raise MemoryStorageError("Memory response missing owner identifier")

    user_id = str(raw_user_id).strip()
    if not user_id:
        raise MemoryStorageError("Memory response contains an empty owner identifier")

    memory_id = getattr(memory, "id", None)
    if memory_id is None:
        raise MemoryStorageError("Memory response missing identifier")
    tier = _resolve_tier(getattr(memory, "tier", None), metadata)
    record = MemoryRecordV1(
        id=str(memory_id),
        tier=tier,
        user_id=user_id,
        content=content,
        metadata=metadata,
    )
    return record


def _ensure_access(record: MemoryRecordV1, current_user: User) -> None:
    """Ensure the current user can operate on the supplied record."""

    expected_user = record.user_id
    if expected_user is None:
        return
    current_id = str(getattr(current_user, "id", ""))
    if expected_user != current_id and not getattr(current_user, "is_admin", False):
        raise MemoryAccessDeniedError("You don't have permission to access this memory")


def _list_params_dependency(
    tier: str | None = Query(None, description="Filter by memory tier"),
    query: str | None = Query(None, description="Search query for memory content"),
    tags: List[str] | None = Query(None, description="Filter by tags"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of memories"),
    offset: int = Query(0, ge=0, description="Number of memories to skip"),
) -> MemoryListParamsV1:
    tag_values = tags or []
    return MemoryListParamsV1(tier=tier, query=query, tags=tag_values, limit=limit, offset=offset)


@router.post(
    "",
    response_model=MemoryRecordV1,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new memory",
    response_model_exclude_unset=True,
)
async def create_memory(
    payload: MemoryCreateRequestV1,
    current_user: User = Depends(authenticate_request),
    memory_service: MemoryService = Depends(get_memory_service),
) -> MemoryRecordV1:
    logger.debug("User %s creating memory", getattr(current_user, "id", "<unknown>"))
    try:
        service_payload = payload.to_service_payload(
            user_id=str(getattr(current_user, "id", "")),
            session_id=getattr(current_user, "session_id", None),
        )
        created = await memory_service.create_memory(service_payload)
        record = _to_memory_record(created)
        return record
    except MemoryTierFullError as exc:
        logger.warning("Memory tier full: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Memory tier is full: {exc}",
        ) from exc
    except MemoryStorageError as exc:
        logger.error("Storage failure while creating memory: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to store memory: {exc}",
        ) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected error creating memory")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while creating the memory",
        ) from exc


@router.get(
    "/{memory_id}",
    response_model=MemoryRecordV1,
    summary="Get a specific memory by ID",
)
async def get_memory(
    memory_id: UUID,
    current_user: User = Depends(authenticate_request),
    memory_service: MemoryService = Depends(get_memory_service),
) -> MemoryRecordV1:
    logger.debug("User %s retrieving memory %s", getattr(current_user, "id", "<unknown>"), memory_id)
    try:
        memory = await memory_service.get_memory(
            memory_id,
            user=current_user,
        )
        record = _to_memory_record(memory)
        _ensure_access(record, current_user)
        return record
    except MemoryNotFoundError as exc:
        logger.warning("Memory %s not found", memory_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Memory with ID {memory_id} not found",
        ) from exc
    except MemoryAccessDeniedError as exc:
        logger.warning("Access denied for memory %s: %s", memory_id, exc)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected error retrieving memory %s", memory_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while retrieving the memory",
        ) from exc


@router.get(
    "",
    response_model=List[MemoryRecordV1],
    summary="List memories",
)
async def list_memories(
    params: MemoryListParamsV1 = Depends(_list_params_dependency),
    current_user: User = Depends(authenticate_request),
    memory_service: MemoryService = Depends(get_memory_service),
) -> List[MemoryRecordV1]:
    logger.debug(
        "User %s listing memories (tier=%s, query=%s, tags=%s)",
        getattr(current_user, "id", "<unknown>"),
        params.tier,
        params.query,
        params.tags,
    )
    try:
        search_params = MemorySearchParams(**params.with_user(str(getattr(current_user, "id", ""))))
        results = await memory_service.list_memories(
            search_params,
            user=current_user,
            roles=getattr(current_user, "roles", []),
            allow_admin=getattr(current_user, "is_admin", False),
        )
        return [_to_memory_record(result) for result in results]
    except Exception as exc:  # noqa: BLE001
        logger.exception("Error listing memories")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while retrieving memories",
        ) from exc


@router.put(
    "/{memory_id}",
    response_model=MemoryRecordV1,
    summary="Update a memory",
)
async def update_memory(
    memory_id: UUID,
    payload: MemoryUpdateRequestV1,
    current_user: User = Depends(authenticate_request),
    memory_service: MemoryService = Depends(get_memory_service),
) -> MemoryRecordV1:
    logger.debug("User %s updating memory %s", getattr(current_user, "id", "<unknown>"), memory_id)
    try:
        existing = await memory_service.get_memory(
            memory_id,
            user=current_user,
        )
        record = _to_memory_record(existing)
        _ensure_access(record, current_user)

        update_payload = payload.to_service_payload()
        updated = await memory_service.update_memory(
            memory_id,
            update_payload,
            user=current_user,
            roles=getattr(current_user, "roles", []),
            allow_admin=getattr(current_user, "is_admin", False),
        )
        return _to_memory_record(updated)
    except MemoryNotFoundError as exc:
        logger.warning("Memory %s not found for update", memory_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Memory with ID {memory_id} not found",
        ) from exc
    except MemoryAccessDeniedError as exc:
        logger.warning("Access denied updating memory %s: %s", memory_id, exc)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    except MemoryStorageError as exc:
        logger.error("Storage error updating memory %s: %s", memory_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update memory: {exc}",
        ) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected error updating memory %s", memory_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while updating the memory",
        ) from exc


@router.delete(
    "/{memory_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a memory",
)
async def delete_memory(
    memory_id: UUID,
    current_user: User = Depends(authenticate_request),
    memory_service: MemoryService = Depends(get_memory_service),
) -> Response:
    logger.debug("User %s deleting memory %s", getattr(current_user, "id", "<unknown>"), memory_id)
    try:
        existing = await memory_service.get_memory(
            memory_id,
            user=current_user,
        )
        record = _to_memory_record(existing)
        _ensure_access(record, current_user)

        await memory_service.delete_memory(memory_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except MemoryNotFoundError as exc:
        logger.warning("Memory %s not found for deletion", memory_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Memory with ID {memory_id} not found",
        ) from exc
    except MemoryAccessDeniedError as exc:
        logger.warning("Access denied deleting memory %s: %s", memory_id, exc)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected error deleting memory %s", memory_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while deleting the memory",
        ) from exc


@router.post(
    "/transfer",
    response_model=MemoryRecordV1,
    summary="Transfer a memory between tiers",
)
async def transfer_memory(
    request: MemoryTransferRequestV1,
    current_user: User = Depends(authenticate_request),
    memory_service: MemoryService = Depends(get_memory_service),
) -> MemoryRecordV1:
    logger.debug(
        "User %s transferring memory %s to %s",
        getattr(current_user, "id", "<unknown>"),
        request.memory_id,
        request.target_tier,
    )
    try:
        existing = await memory_service.get_memory(
            UUID(str(request.memory_id)),
            user=current_user,
        )
        record = _to_memory_record(existing)
        _ensure_access(record, current_user)

        transferred = await memory_service.transfer_memory(
            UUID(str(request.memory_id)),
            request.target_tier,
        )
        return _to_memory_record(transferred)
    except MemoryNotFoundError as exc:
        logger.warning("Memory %s not found for transfer", request.memory_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Memory with ID {request.memory_id} not found",
        ) from exc
    except MemoryAccessDeniedError as exc:
        logger.warning(
            "Access denied transferring memory %s: %s",
            request.memory_id,
            exc,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    except MemoryStorageError as exc:
        logger.error("Storage error transferring memory %s: %s", request.memory_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to transfer memory: {exc}",
        ) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "Unexpected error transferring memory %s", request.memory_id
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while transferring the memory",
        ) from exc


__all__ = ["router", "get_memory_service"]
