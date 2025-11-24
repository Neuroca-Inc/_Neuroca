"""Memory retrieval helpers for the asynchronous memory manager."""

from __future__ import annotations

from typing import Any, Optional

from neuroca.core.exceptions import MemoryAccessDeniedError
from neuroca.memory.exceptions import InvalidTierError, MemoryManagerOperationError
from neuroca.memory.manager.components.base import LOGGER
from neuroca.memory.manager.scoping import MemoryRetrievalScope

from .support import MemoryManagerOperationSupportMixin


class MemoryManagerRetrieveMixin(MemoryManagerOperationSupportMixin):
    """Expose scoped retrieval helpers across memory tiers."""

    async def retrieve_memory(
        self,
        memory_id: str,
        tier: Optional[str] = None,
        scope: MemoryRetrievalScope | None = None,
    ) -> Any | None:
        """Retrieve a memory by ``memory_id`` optionally constrained to ``tier``."""

        self._ensure_initialized()

        scope_obj = self._normalize_scope(scope)
        try:
            if tier:
                return await self._retrieve_from_specific_tier(memory_id, tier, scope_obj)
            return await self._retrieve_from_any_tier(memory_id, scope_obj)
        except MemoryAccessDeniedError:
            raise
        except InvalidTierError:
            raise
        except Exception as exc:  # noqa: BLE001
            LOGGER.exception("Failed to retrieve memory %s", memory_id)
            raise MemoryManagerOperationError(
                f"Failed to retrieve memory: {exc}"
            ) from exc

    async def _retrieve_from_specific_tier(
        self,
        memory_id: str,
        tier: str,
        scope: MemoryRetrievalScope,
    ) -> Any | None:
        """Fetch ``memory_id`` from a specific tier with scope enforcement."""

        tier_instance = self._get_tier_by_name(tier)
        memory_data = await tier_instance.retrieve(memory_id)
        if not memory_data:
            return None

        metadata = self._extract_metadata_dict(memory_data)
        self._assert_memory_access(memory_id, metadata, scope, "retrieve")
        await tier_instance.access(memory_id)
        return memory_data

    async def _retrieve_from_any_tier(
        self,
        memory_id: str,
        scope: MemoryRetrievalScope,
    ) -> Any | None:
        """Search through all tiers for ``memory_id`` respecting ``scope``."""

        for tier_name in self._tier_iteration_order():
            memory_data = await self._retrieve_from_specific_tier(
                memory_id,
                tier_name,
                scope,
            )
            if memory_data:
                return memory_data
        return None


__all__ = ["MemoryManagerRetrieveMixin"]
