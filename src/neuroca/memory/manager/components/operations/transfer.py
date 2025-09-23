"""Memory transfer helpers for the asynchronous memory manager."""

from __future__ import annotations

import contextlib
from datetime import datetime, timezone
from typing import Any, Optional

from neuroca.memory.exceptions import (
    InvalidTierError,
    MemoryManagerOperationError,
    MemoryNotFoundError,
)
from neuroca.memory.manager.components.base import LOGGER

from .support import MemoryManagerOperationSupportMixin


class MemoryManagerTransferMixin(MemoryManagerOperationSupportMixin):
    """Move memories between tiers while preserving metadata."""

    async def transfer_memory(
        self,
        memory_id: str,
        target_tier: str,
    ) -> Any:
        """Move ``memory_id`` into ``target_tier`` and return the transferred item."""

        self._ensure_initialized()

        try:
            resolved_target = self._resolve_tier_key(target_tier)
        except ValueError as exc:  # noqa: B904
            raise InvalidTierError(f"Unknown target tier: {target_tier!r}") from exc

        source_tier_name, memory_item = await self._locate_memory(memory_id)
        if source_tier_name is None or memory_item is None:
            raise MemoryNotFoundError(f"Memory {memory_id} not found in any tier")
        if source_tier_name == resolved_target:
            return memory_item

        source_tier = self._get_tier_by_name(source_tier_name)
        target_tier_instance = self._get_tier_by_name(resolved_target)
        payload = self._prepare_transfer_payload(memory_item, resolved_target)

        await self._store_in_target(target_tier_instance, payload, memory_id, resolved_target)
        await self._remove_from_source(source_tier, memory_id, source_tier_name)
        self._remove_from_working_memory(memory_id)
        return await self._fetch_transferred_item(target_tier_instance, memory_id)

    async def _locate_memory(
        self,
        memory_id: str,
    ) -> tuple[Optional[str], Optional[Any]]:
        """Return the tier name and memory item for ``memory_id``."""

        for tier_name in self._tier_iteration_order():
            tier_instance = self._get_tier_by_name(tier_name)
            fetched = await tier_instance.retrieve(memory_id)
            if fetched:
                return tier_name, self._coerce_memory_item(fetched)
        return None, None

    def _prepare_transfer_payload(
        self,
        memory_item: Any,
        target_tier: str,
    ) -> dict[str, Any]:
        """Return the serialised payload for ``memory_item`` targeting ``target_tier``."""

        metadata = getattr(memory_item, "metadata", None)
        if metadata is not None:
            with contextlib.suppress(Exception):
                metadata.tier = target_tier
                if hasattr(metadata, "updated_at"):
                    metadata.updated_at = datetime.now(timezone.utc)

        try:
            return memory_item.model_dump()
        except Exception:  # noqa: BLE001
            return memory_item.dict()

    async def _store_in_target(
        self,
        target_tier,
        payload: dict[str, Any],
        memory_id: str,
        target_tier_name: str,
    ) -> None:
        """Persist ``payload`` in ``target_tier``."""

        try:
            await target_tier.store(payload, memory_id=memory_id)
        except Exception as exc:  # noqa: BLE001
            LOGGER.exception(
                "Failed to transfer memory %s to %s",
                memory_id,
                target_tier_name,
            )
            raise MemoryManagerOperationError(
                f"Failed to move memory to {target_tier_name}: {exc}"
            ) from exc

    async def _remove_from_source(
        self,
        source_tier,
        memory_id: str,
        source_tier_name: str,
    ) -> None:
        """Best-effort deletion from the source tier."""

        try:
            await source_tier.delete(memory_id)
        except Exception:  # noqa: BLE001
            LOGGER.warning(
                "Failed to delete memory %s from %s after transfer",
                memory_id,
                source_tier_name,
                exc_info=True,
            )

    def _remove_from_working_memory(self, memory_id: str) -> None:
        """Remove ``memory_id`` from the working-memory buffer when present."""

        if getattr(self, "_working_memory", None) and self._working_memory.contains(memory_id):
            self._working_memory.remove_item(memory_id)

    async def _fetch_transferred_item(
        self,
        target_tier,
        memory_id: str,
    ) -> Any:
        """Return the transferred memory item."""

        moved = await target_tier.retrieve(memory_id)
        return self._coerce_memory_item(moved)


__all__ = ["MemoryManagerTransferMixin"]
