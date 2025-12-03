"""Versioned FastAPI routes for memory operations (v1)."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
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
from neuroca.core.services.metrics import MetricsService
from neuroca.api.routes.metrics import get_metrics_service
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
    RateLimitExceededError,
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


def _estimate_record_size_bytes(record: MemoryRecordV1) -> int:
    """Approximate serialized size of a memory record for metering.

    This is a best-effort approximation used only for usage gauges.
    Failures return 0 and are treated as a no-op for storage metrics.
    """
    try:
        size = 0
        content = getattr(record, "content", None)
        if content is not None:
            text = getattr(content, "text", None)
            if isinstance(text, str):
                size += len(text.encode("utf-8"))
            raw = getattr(content, "raw_content", None)
            if raw is not None:
                raw_str = raw if isinstance(raw, str) else str(raw)
                size += len(raw_str.encode("utf-8"))
        metadata = getattr(record, "metadata", None)
        if metadata is not None:
            payload = metadata.model_dump()
            size += len(str(payload).encode("utf-8"))
        return size
    except Exception:
        return 0


MEMORY_DAILY_WRITE_LIMIT = 10_000
MEMORY_SOFT_QUOTA_PERIOD = timedelta(hours=24)
MEMORY_SOFT_QUOTA_NEAR_LIMIT_RATIO = 0.8
MEMORY_SOFT_QUOTA_METRIC_NEAR = "usage.quota.memory.near_limit"
MEMORY_SOFT_QUOTA_METRIC_EXCEEDED = "usage.quota.memory.exceeded"


async def _enforce_memory_soft_quota(
    *,
    metrics_service: MetricsService,
    current_user: User,
) -> None:
    """Best-effort enforcement of per-tenant memory write soft quotas.

    This helper consults the in-memory MetricsService for the last 24 hours of
    memory write activity for the current tenant. When the configured limit is
    exceeded it raises an HTTP 429 error; when a near-limit threshold is
    crossed it records a separate quota metric but allows the request to
    proceed.
    """
    if MEMORY_DAILY_WRITE_LIMIT <= 0:
        return

    now = datetime.utcnow()
    window_start = now - MEMORY_SOFT_QUOTA_PERIOD
    tenant_id = getattr(current_user, "tenant_id", None)
    labels = {
        "tenant_id": str(tenant_id).strip() if tenant_id is not None else "unknown",
    }

    try:
        total_writes = 0.0
        for op_name in ("create", "update", "delete"):
            metric_name = f"usage.memory.operations.{op_name}"
            try:
                data = await metrics_service.get_metric_data(
                    name=metric_name,
                    start_time=window_start,
                    end_time=now,
                    interval="1h",
                    aggregation=None,
                    limit=10_000,
                    labels=labels,
                )
            except KeyError:
                continue
            total_writes += sum(float(point["value"]) for point in data.points)

        ratio = total_writes / float(MEMORY_DAILY_WRITE_LIMIT)
        if total_writes >= MEMORY_DAILY_WRITE_LIMIT:
            await metrics_service.record_metric(
                name=MEMORY_SOFT_QUOTA_METRIC_EXCEEDED,
                value=1,
                labels=labels,
            )
            exc = RateLimitExceededError(
                limit=MEMORY_DAILY_WRITE_LIMIT,
                window="24h",
            )
            logger.warning(
                "Memory soft quota exceeded for tenant=%s: %s",
                labels["tenant_id"],
                exc,
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=str(exc),
            ) from exc
        if ratio >= MEMORY_SOFT_QUOTA_NEAR_LIMIT_RATIO:
            await metrics_service.record_metric(
                name=MEMORY_SOFT_QUOTA_METRIC_NEAR,
                value=1,
                labels=labels,
            )
    except HTTPException:
        raise
    except Exception:
        logger.debug(
            "Memory soft quota check failed; continuing without enforcement",
            exc_info=True,
        )


def _ensure_access(
    record: MemoryRecordV1, current_user: User, *, operation: str
) -> None:
    """Ensure the current user can operate on the supplied record."""
 
    expected_user = record.user_id
    if expected_user is None:
        return
 
    if getattr(current_user, "is_admin", False):
        return
 
    expected_identifier = str(expected_user).strip()
    if not expected_identifier:
        # If the record does not advertise an owner after validation we treat it as
        # unscoped and allow the operation to proceed.
        return
 
    raw_current_id = getattr(current_user, "id", None)
    current_identifier = (
        str(raw_current_id).strip() if raw_current_id is not None else ""
    )
 
    if not current_identifier:
        raise MemoryAccessDeniedError(
            record.id,
            "<unknown>",
            operation,
            "Authenticated user is missing an identifier required for access validation.",
        )
 
    record_tenant = getattr(record.metadata, "tenant_id", None)
    current_tenant = getattr(current_user, "tenant_id", None)
    normalized_record_tenant = (
        str(record_tenant).strip() if record_tenant is not None else ""
    )
    normalized_current_tenant = (
        str(current_tenant).strip() if current_tenant is not None else ""
    )
 
    if (
        normalized_record_tenant
        and normalized_current_tenant
        and normalized_record_tenant != normalized_current_tenant
    ):
        raise MemoryAccessDeniedError(
            record.id,
            current_identifier,
            operation,
            (
                "Tenant mismatch between record and authenticated principal; "
                "cross-tenant access is not permitted."
            ),
        )
 
    if expected_identifier != current_identifier:
        raise MemoryAccessDeniedError(record.id, current_identifier, operation)


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
    metrics_service: MetricsService = Depends(get_metrics_service),
) -> MemoryRecordV1:
    await _enforce_memory_soft_quota(
        metrics_service=metrics_service,
        current_user=current_user,
    )
    logger.debug("User %s creating memory", getattr(current_user, "id", "<unknown>"))
    try:
        service_payload = payload.to_service_payload(
            user_id=str(getattr(current_user, "id", "")),
            session_id=getattr(current_user, "session_id", None),
            tenant_id=getattr(current_user, "tenant_id", None),
        )
        created = await memory_service.create_memory(service_payload)
        record = _to_memory_record(created)
        # Best-effort per-tenant metering for memory creation.
        try:
            tenant_id = getattr(current_user, "tenant_id", None)
            user_id = getattr(current_user, "id", None)
            size_bytes = _estimate_record_size_bytes(record)
            await metrics_service.record_memory_operation(
                tenant_id=str(tenant_id).strip() if tenant_id is not None else None,
                user_id=str(user_id).strip() if user_id is not None else None,
                operation="create",
                tier=record.tier,
                size_bytes=size_bytes or None,
            )
        except Exception:
            logger.debug("Failed to record create_memory usage metrics", exc_info=True)
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
    metrics_service: MetricsService = Depends(get_metrics_service),
) -> MemoryRecordV1:
    logger.debug("User %s retrieving memory %s", getattr(current_user, "id", "<unknown>"), memory_id)
    try:
        memory = await memory_service.get_memory(
            memory_id,
            user=current_user,
        )
        record = _to_memory_record(memory)
        _ensure_access(record, current_user, operation="read")
        # Best-effort metering for single-record read.
        try:
            tenant_id = getattr(current_user, "tenant_id", None)
            user_id = getattr(current_user, "id", None)
            await metrics_service.record_memory_operation(
                tenant_id=str(tenant_id).strip() if tenant_id is not None else None,
                user_id=str(user_id).strip() if user_id is not None else None,
                operation="read",
                tier=record.tier,
                size_bytes=None,
            )
        except Exception:
            logger.debug("Failed to record get_memory usage metrics", exc_info=True)
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
        search_params = MemorySearchParams(
            **params.with_user(
                str(getattr(current_user, "id", "")),
                tenant_id=str(getattr(current_user, "tenant_id", "")).strip() or None,
            )
        )
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
    metrics_service: MetricsService = Depends(get_metrics_service),
) -> MemoryRecordV1:
    await _enforce_memory_soft_quota(
        metrics_service=metrics_service,
        current_user=current_user,
    )
    logger.debug("User %s updating memory %s", getattr(current_user, "id", "<unknown>"), memory_id)
    try:
        existing = await memory_service.get_memory(
            memory_id,
            user=current_user,
        )
        record = _to_memory_record(existing)
        _ensure_access(record, current_user, operation="update")

        update_payload = payload.to_service_payload()
        updated = await memory_service.update_memory(
            memory_id,
            update_payload,
            user=current_user,
            roles=getattr(current_user, "roles", []),
            allow_admin=getattr(current_user, "is_admin", False),
        )
        updated_record = _to_memory_record(updated)
        # Best-effort metering for update operations.
        try:
            tenant_id = getattr(current_user, "tenant_id", None)
            user_id = getattr(current_user, "id", None)
            await metrics_service.record_memory_operation(
                tenant_id=str(tenant_id).strip() if tenant_id is not None else None,
                user_id=str(user_id).strip() if user_id is not None else None,
                operation="update",
                tier=updated_record.tier,
                size_bytes=None,
            )
        except Exception:
            logger.debug("Failed to record update_memory usage metrics", exc_info=True)
        return updated_record
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
    metrics_service: MetricsService = Depends(get_metrics_service),
) -> Response:
    await _enforce_memory_soft_quota(
        metrics_service=metrics_service,
        current_user=current_user,
    )
    logger.debug("User %s deleting memory %s", getattr(current_user, "id", "<unknown>"), memory_id)
    try:
        existing = await memory_service.get_memory(
            memory_id,
            user=current_user,
        )
        record = _to_memory_record(existing)
        _ensure_access(record, current_user, operation="delete")

        # Best-effort metering for delete operations, including storage gauge.
        try:
            tenant_id = getattr(current_user, "tenant_id", None)
            user_id = getattr(current_user, "id", None)
            size_bytes = _estimate_record_size_bytes(record)
            await metrics_service.record_memory_operation(
                tenant_id=str(tenant_id).strip() if tenant_id is not None else None,
                user_id=str(user_id).strip() if user_id is not None else None,
                operation="delete",
                tier=record.tier,
                size_bytes=size_bytes or None,
            )
        except Exception:
            logger.debug("Failed to record delete_memory usage metrics", exc_info=True)

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
    metrics_service: MetricsService = Depends(get_metrics_service),
) -> MemoryRecordV1:
    await _enforce_memory_soft_quota(
        metrics_service=metrics_service,
        current_user=current_user,
    )
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
        _ensure_access(record, current_user, operation="transfer")

        transferred = await memory_service.transfer_memory(
            UUID(str(request.memory_id)),
            request.target_tier,
        )
        new_record = _to_memory_record(transferred)
        # Best-effort metering: model transfer as delete from old tier + create in new tier.
        try:
            tenant_id = getattr(current_user, "tenant_id", None)
            user_id = getattr(current_user, "id", None)
            size_bytes = _estimate_record_size_bytes(record)
            normalized_tenant = (
                str(tenant_id).strip() if tenant_id is not None else None
            )
            normalized_user = str(user_id).strip() if user_id is not None else None
            await metrics_service.record_memory_operation(
                tenant_id=normalized_tenant,
                user_id=normalized_user,
                operation="delete",
                tier=record.tier,
                size_bytes=size_bytes or None,
            )
            await metrics_service.record_memory_operation(
                tenant_id=normalized_tenant,
                user_id=normalized_user,
                operation="create",
                tier=new_record.tier,
                size_bytes=size_bytes or None,
            )
        except Exception:
            logger.debug("Failed to record transfer_memory usage metrics", exc_info=True)
        return new_record
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
