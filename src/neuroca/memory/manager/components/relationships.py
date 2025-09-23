"""Relationship management helpers for long-term memory."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Mapping

from neuroca.memory.exceptions import MemoryManagerOperationError, MemoryNotFoundError, TierOperationError
from neuroca.memory.models.memory_item import MemoryItem

from .base import LOGGER


class MemoryManagerRelationshipsMixin:
    """Expose relationship CRUD operations on the memory manager."""

    async def add_relationship(
        self,
        source_id: str,
        target_id: str,
        relationship_type: str,
        *,
        strength: float = 0.5,
        bidirectional: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Create a relationship between two long-term memories."""

        self._ensure_initialized()

        if not source_id or not target_id:
            raise MemoryManagerOperationError("source_id and target_id are required")

        normalized_type = relationship_type.strip().lower()
        if not normalized_type:
            raise MemoryManagerOperationError("relationship_type cannot be empty")

        metadata_payload: Dict[str, Any] | None = None
        if metadata is not None:
            if not isinstance(metadata, Mapping):
                raise MemoryManagerOperationError("metadata must be a mapping")
            metadata_payload = dict(metadata)

        try:
            success = await self.ltm_storage.add_relationship(
                source_id=source_id,
                target_id=target_id,
                relationship_type=normalized_type,
                strength=strength,
                bidirectional=bidirectional,
                metadata=metadata_payload,
            )
        except (MemoryNotFoundError, ValueError):
            raise
        except TierOperationError as exc:
            raise MemoryManagerOperationError(
                f"Failed to add relationship: {exc}"
            ) from exc
        except Exception as exc:
            LOGGER.exception("Failed to add relationship %s -> %s", source_id, target_id)
            raise MemoryManagerOperationError(
                f"Failed to add relationship: {exc}"
            ) from exc

        if not success:
            raise MemoryManagerOperationError("Relationship creation did not succeed")

        return True

    async def remove_relationship(
        self,
        source_id: str,
        target_id: str,
        *,
        bidirectional: bool = True,
    ) -> bool:
        """Remove an existing relationship between two memories."""

        self._ensure_initialized()

        try:
            success = await self.ltm_storage.remove_relationship(
                source_id=source_id,
                target_id=target_id,
                bidirectional=bidirectional,
            )
        except MemoryNotFoundError:
            raise
        except TierOperationError as exc:
            raise MemoryManagerOperationError(
                f"Failed to remove relationship: {exc}"
            ) from exc
        except Exception as exc:
            LOGGER.exception(
                "Failed to remove relationship %s -> %s", source_id, target_id
            )
            raise MemoryManagerOperationError(
                f"Failed to remove relationship: {exc}"
            ) from exc

        if not success:
            raise MemoryManagerOperationError("Relationship removal did not succeed")

        return True

    async def get_related_memories(
        self,
        memory_id: str,
        *,
        relationship_type: Optional[str] = None,
        min_strength: float = 0.0,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Return memories connected to the supplied long-term memory."""

        self._ensure_initialized()

        normalized_type = relationship_type.strip().lower() if relationship_type else None

        try:
            raw_related = await self.ltm_storage.get_related_memories(
                memory_id=memory_id,
                relationship_type=normalized_type,
                min_strength=min_strength,
                limit=limit,
            )
        except MemoryNotFoundError:
            raise
        except TierOperationError as exc:
            raise MemoryManagerOperationError(
                f"Failed to load related memories: {exc}"
            ) from exc
        except Exception as exc:
            LOGGER.exception("Failed to load related memories for %s", memory_id)
            raise MemoryManagerOperationError(
                f"Failed to load related memories: {exc}"
            ) from exc

        results: List[Dict[str, Any]] = []
        for raw in raw_related:
            relationship_meta: Dict[str, Any] = {}
            payload = raw
            if isinstance(raw, dict):
                relationship_meta = dict(raw.get("_relationship", {}))
                payload = {k: v for k, v in raw.items() if k != "_relationship"}

            try:
                memory_item = (
                    payload if isinstance(payload, MemoryItem) else MemoryItem.model_validate(payload)
                )
            except Exception as exc:
                raise MemoryManagerOperationError(
                    "Failed to deserialize related memory payload"
                ) from exc

            results.append(
                {
                    "memory": memory_item,
                    "relationship": relationship_meta,
                    "tier": self.LTM_TIER,
                }
            )

        return results

    async def list_relationship_types(self) -> Dict[str, str]:
        """List the supported relationship types exposed by LTM."""

        self._ensure_initialized()

        try:
            return await self.ltm_storage.get_relationship_types()
        except Exception as exc:
            LOGGER.exception("Failed to retrieve LTM relationship types")
            raise MemoryManagerOperationError(
                f"Failed to retrieve relationship types: {exc}"
            ) from exc


__all__ = ["MemoryManagerRelationshipsMixin"]
