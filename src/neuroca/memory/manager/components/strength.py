"""Memory strengthening helpers."""

from __future__ import annotations

from typing import Optional

from neuroca.memory.exceptions import InvalidTierError, MemoryManagerOperationError, MemoryNotFoundError

from .base import LOGGER


class MemoryManagerStrengthMixin:
    """Expose APIs for reinforcing stored memories."""

    async def strengthen_memory(
        self,
        memory_id: str,
        tier: Optional[str] = None,
        strengthen_amount: float = 0.1,
    ) -> bool:
        """Strengthen a memory to make it less likely to be forgotten."""

        self._ensure_initialized()

        try:
            success = False

            if tier:
                tier_instance = self._get_tier_by_name(tier)
                return await tier_instance.strengthen(memory_id, strengthen_amount)

            for tier_name in [self.STM_TIER, self.MTM_TIER, self.LTM_TIER]:
                tier_instance = self._get_tier_by_name(tier_name)
                if await tier_instance.exists(memory_id):
                    if await tier_instance.strengthen(memory_id, strengthen_amount):
                        success = True
                    break

            return success
        except Exception as exc:
            if isinstance(exc, (InvalidTierError, MemoryNotFoundError)):
                raise

            LOGGER.exception("Failed to strengthen memory %s", memory_id)
            raise MemoryManagerOperationError(
                f"Failed to strengthen memory: {exc}"
            ) from exc


__all__ = ["MemoryManagerStrengthMixin"]
