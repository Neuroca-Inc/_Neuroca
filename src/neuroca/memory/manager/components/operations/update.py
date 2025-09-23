"""Memory update helpers for the asynchronous memory manager."""

from __future__ import annotations

from typing import Any, Dict, Mapping, Optional

from neuroca.core.exceptions import MemoryValidationError
from neuroca.memory.exceptions import MemoryManagerOperationError, MemoryNotFoundError
from neuroca.memory.manager.components.base import LOGGER
from neuroca.memory.models.memory_item import MemoryItem, MemoryMetadata

from .support import MemoryManagerOperationSupportMixin


class MemoryManagerUpdateMixin(MemoryManagerOperationSupportMixin):
    """Implement metadata and content updates for stored memories."""

    async def update_memory(
        self,
        memory_id: str,
        content: Optional[Any] = None,
        summary: Optional[str] = None,
        importance: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[list[str]] = None,
    ) -> bool:
        """Update ``memory_id`` with sanitised content and metadata."""

        self._ensure_initialized()

        try:
            memory_item = await self.retrieve_memory(memory_id)
            if not memory_item:
                raise MemoryNotFoundError(f"Memory {memory_id} not found")

            metadata_source, tier_name = self._determine_update_source(memory_item)
            content_updates = self._prepare_content_updates(content, summary)
            metadata_updates = self._prepare_metadata_updates(
                metadata_source,
                metadata,
                tags,
                importance,
            )

            tier_instance = self._get_tier_by_name(tier_name)
            return await tier_instance.update(
                memory_id,
                content=content_updates or None,
                metadata=metadata_updates or None,
            )
        except MemoryValidationError:
            raise
        except Exception as exc:  # noqa: BLE001
            LOGGER.exception("Failed to update memory %s", memory_id)
            raise MemoryManagerOperationError(
                f"Failed to update memory: {exc}"
            ) from exc

    def _determine_update_source(
        self,
        memory_item: Any,
    ) -> tuple[Dict[str, Any], str]:
        """Return a mutable metadata mapping and tier for ``memory_item``."""

        if isinstance(memory_item, MemoryItem):
            metadata = memory_item.metadata.model_dump()
            tier = memory_item.metadata.tier or self.LTM_TIER
            return metadata, tier

        if isinstance(memory_item, Mapping):
            metadata_field = memory_item.get("metadata", {})
            if isinstance(metadata_field, MemoryMetadata):
                metadata = metadata_field.model_dump()
            elif isinstance(metadata_field, Mapping):
                metadata = dict(metadata_field)
            else:
                metadata = {}
            tier = metadata.get("tier") or self.LTM_TIER
            return metadata, tier

        return {}, self.LTM_TIER

    def _prepare_content_updates(
        self,
        content: Optional[Any],
        summary: Optional[str],
    ) -> Dict[str, Any]:
        """Return sanitised content update payloads."""

        updates: Dict[str, Any] = {}
        if content is not None:
            sanitized_content = self._sanitizer.sanitize_content(content)
            if sanitized_content:
                updates.update(sanitized_content)
        if summary is not None:
            updates["summary"] = self._sanitizer.sanitize_text("summary", summary)
        return updates

    def _prepare_metadata_updates(
        self,
        metadata_source: Mapping[str, Any],
        metadata: Optional[Dict[str, Any]],
        tags: Optional[list[str]],
        importance: Optional[float],
    ) -> Dict[str, Any]:
        """Return sanitised metadata update payloads."""

        updates: Dict[str, Any] = {}
        metadata_tag_map: Dict[str, Any] = {}

        if importance is not None:
            updates["importance"] = importance

        if metadata is not None:
            sanitized_metadata, metadata_tag_map = self._sanitizer.sanitize_metadata(metadata)
            updates.update(sanitized_metadata)

        existing_tags = self._sanitizer.sanitize_tag_map(metadata_source.get("tags", {}))
        explicit_tags = (
            self._sanitizer.sanitize_tag_list(tags)
            if tags is not None
            else {}
        )
        combined_tags = self._sanitizer.merge_tag_maps(
            existing_tags,
            metadata_tag_map,
            explicit_tags,
        )
        if tags is not None or metadata_tag_map or combined_tags != existing_tags:
            updates["tags"] = combined_tags
        return updates


__all__ = ["MemoryManagerUpdateMixin"]
