"""Memory deletion helpers for the asynchronous memory manager."""

from __future__ import annotations

from typing import Optional

from neuroca.memory.exceptions import InvalidTierError, MemoryManagerOperationError
from neuroca.memory.manager.components.base import LOGGER

from .support import MemoryManagerOperationSupportMixin


class MemoryManagerDeleteMixin(MemoryManagerOperationSupportMixin):
    """Provide deletion helpers across memory tiers."""

    async def delete_memory(
        self,
        memory_id: str,
        tier: Optional[str] = None,
    ) -> bool:
        """Delete ``memory_id`` either from ``tier`` or across all tiers."""

        self._ensure_initialized()

        try:
            if tier:
                success = await self._delete_from_tier(memory_id, tier)
            else:
                success = await self._delete_from_all_tiers(memory_id)

            if success:
                self._working_memory.remove_item(memory_id)
            return success
        except InvalidTierError:
            raise
        except Exception as exc:  # noqa: BLE001
            LOGGER.exception("Failed to delete memory %s", memory_id)
            raise MemoryManagerOperationError(
                f"Failed to delete memory: {exc}"
            ) from exc

    async def _delete_from_tier(self, memory_id: str, tier_name: str) -> bool:
        """Delete ``memory_id`` from ``tier_name``."""

        tier_instance = self._get_tier_by_name(tier_name)
        return await tier_instance.delete(memory_id)

    async def _delete_from_all_tiers(self, memory_id: str) -> bool:
        """Attempt deletion across every configured tier."""

        success = False
        for tier_name in self._tier_iteration_order():
            tier_instance = self._get_tier_by_name(tier_name)
            if await tier_instance.delete(memory_id):
                success = True
        return success


__all__ = ["MemoryManagerDeleteMixin"]
