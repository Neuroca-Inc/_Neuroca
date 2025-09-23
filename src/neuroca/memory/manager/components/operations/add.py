"""Memory creation helpers for the asynchronous memory manager."""

from __future__ import annotations

import asyncio
import contextlib
from typing import Any, Dict, List, Mapping, Optional

from neuroca.memory.exceptions import (
    MemoryBackpressureError,
    MemoryCapacityError,
    MemoryManagerOperationError,
)
from neuroca.memory.manager.components.base import LOGGER
from neuroca.memory.models.memory_item import MemoryContent, MemoryItem, MemoryMetadata
from neuroca.memory.models.working_memory import WorkingMemoryItem

from .support import MemoryManagerOperationSupportMixin


class MemoryManagerAddMixin(MemoryManagerOperationSupportMixin):
    """Implement creation operations for the memory manager."""

    async def add_memory(
        self,
        content: Any,
        summary: Optional[str] = None,
        importance: float = 0.5,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        embedding: Optional[List[float]] = None,
        initial_tier: Optional[str] = None,
    ) -> str:
        """Add a sanitised memory item to ``initial_tier`` and return its ID."""

        del embedding  # Retained for signature compatibility.
        self._ensure_initialized()

        tier_name = self._resolve_initial_tier(initial_tier)
        tier = self._get_tier_by_name(tier_name)

        memory_item = self._build_memory_item(
            content,
            summary,
            importance,
            metadata,
            tags,
            tier_name,
        )
        serialized_memory = self._serialize_memory_item(memory_item)
        memory_id = await self._store_memory_with_backpressure(
            tier_name,
            tier,
            serialized_memory,
            importance,
        )

        await self._maybe_prime_working_memory(memory_id, tier_name, importance, tier)
        await self._audit_creation(serialized_memory, memory_id, tier_name)
        return memory_id

    def _resolve_initial_tier(self, initial_tier: Optional[str]) -> str:
        """Resolve the requested tier name, defaulting to STM."""

        return initial_tier or self.STM_TIER

    def _build_memory_item(
        self,
        content: Any,
        summary: Optional[str],
        importance: float,
        metadata: Optional[Dict[str, Any]],
        tags: Optional[List[str]],
        tier_name: str,
    ) -> MemoryItem:
        """Create a :class:`MemoryItem` from the supplied arguments."""

        sanitized_summary = self._sanitizer.sanitize_optional_text("summary", summary)
        memory_content = self._build_memory_content(content, sanitized_summary)
        memory_metadata = self._build_memory_metadata(
            importance,
            metadata,
            tags,
            tier_name,
        )
        return MemoryItem(content=memory_content, metadata=memory_metadata)

    def _build_memory_content(
        self,
        content: Any,
        sanitized_summary: Optional[str],
    ) -> MemoryContent:
        """Return a sanitised :class:`MemoryContent` instance."""

        text_value, json_payload, raw_payload = self._normalise_content_payload(content)
        return MemoryContent(
            text=text_value,
            summary=sanitized_summary,
            json_data=json_payload if text_value is None else None,
            raw_content=raw_payload if text_value is None else None,
        )

    def _normalise_content_payload(self, content: Any) -> tuple[Any | None, dict[str, Any] | None, Any | None]:
        """Sanitise ``content`` and split it into structured components."""

        if isinstance(content, str):
            return self._sanitizer.sanitize_text("content", content), None, None

        sanitized = self._sanitizer.sanitize_value("content", content)
        if isinstance(sanitized, dict):
            return None, sanitized, None
        return None, None, sanitized

    def _build_memory_metadata(
        self,
        importance: float,
        metadata: Optional[Dict[str, Any]],
        tags: Optional[List[str]],
        tier_name: str,
    ) -> MemoryMetadata:
        """Sanitise metadata fields and construct a :class:`MemoryMetadata` instance."""

        metadata_mapping = self._prepare_metadata_mapping(metadata)
        sanitized_metadata, metadata_tags = self._sanitizer.sanitize_metadata(metadata_mapping)
        core_metadata, extra_metadata = self._partition_metadata_fields(sanitized_metadata)
        sanitized_tag_map = self._sanitizer.merge_tag_maps(
            metadata_tags,
            self._sanitizer.sanitize_tag_list(tags or []),
        )

        memory_metadata = MemoryMetadata(
            importance=importance,
            tags=sanitized_tag_map,
            **core_metadata,
        )
        self._apply_additional_metadata(memory_metadata, extra_metadata)
        self._ensure_metadata_tier(memory_metadata, tier_name)
        return memory_metadata

    def _prepare_metadata_mapping(
        self, metadata: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Ensure ``metadata`` is a dictionary suitable for sanitisation."""

        if metadata is None:
            return {}
        if isinstance(metadata, dict):
            return metadata
        return {"data": metadata}

    def _apply_additional_metadata(
        self,
        memory_metadata: MemoryMetadata,
        extra_metadata: Mapping[str, Any],
    ) -> None:
        """Populate ``additional_metadata`` while respecting nested payloads."""

        if not extra_metadata:
            return

        extra_dict = dict(extra_metadata)
        nested_additional = extra_dict.pop("additional_metadata", None)

        if isinstance(nested_additional, Mapping):
            try:
                memory_metadata.additional_metadata.update(nested_additional)
            except Exception:  # noqa: BLE001
                for key, value in nested_additional.items():
                    memory_metadata.additional_metadata[key] = value
        elif nested_additional is not None:
            memory_metadata.additional_metadata["additional_metadata"] = nested_additional

        for key, value in extra_dict.items():
            memory_metadata.additional_metadata[key] = value

    def _ensure_metadata_tier(
        self,
        memory_metadata: MemoryMetadata,
        tier_name: str,
    ) -> None:
        """Ensure ``memory_metadata`` records the tier where it is stored."""

        with contextlib.suppress(Exception):
            if not getattr(memory_metadata, "tier", None):
                memory_metadata.tier = tier_name

    def _serialize_memory_item(self, memory_item: MemoryItem) -> Dict[str, Any]:
        """Serialise ``memory_item`` with graceful fallbacks."""

        try:
            return memory_item.model_dump()
        except Exception as ser_err:  # noqa: BLE001
            LOGGER.debug(
                "model_dump() failed for MemoryItem: %s; falling back to dict()",
                ser_err,
            )
        try:
            return memory_item.dict()
        except Exception as dict_err:  # noqa: BLE001
            LOGGER.debug(
                "dict() failed for MemoryItem: %s; falling back to manual mapping",
                dict_err,
            )

        content_payload = self._dump_component(memory_item.content)
        metadata_payload = self._dump_component(memory_item.metadata)
        payload = {
            "id": getattr(memory_item, "id", None),
            "content": content_payload,
            "metadata": metadata_payload,
            "summary": getattr(memory_item, "summary", None),
            "embedding": getattr(memory_item, "embedding", None),
        }
        return {key: value for key, value in payload.items() if value is not None}

    def _dump_component(self, component: Any) -> Any:
        """Return a serialisable representation of ``component``."""

        if hasattr(component, "model_dump"):
            try:
                return component.model_dump()
            except Exception:  # noqa: BLE001
                pass
        if hasattr(component, "dict"):
            try:
                return component.dict()
            except Exception:  # noqa: BLE001
                pass
        return component

    async def _store_memory_with_backpressure(
        self,
        tier_name: str,
        tier: Any,
        serialized_memory: Dict[str, Any],
        importance: float,
    ) -> str:
        """Persist ``serialized_memory`` while enforcing backpressure controls."""

        del importance  # Reserved for future weighting rules.
        memory_id: str | None = None
        try:
            async with self._backpressure.slot(tier_name):
                await self._resource_watchdog.ensure_capacity(tier_name, tier)
                memory_id = await self._resource_watchdog.store(
                    tier_name,
                    tier,
                    serialized_memory,
                )
        except MemoryBackpressureError as exc:
            LOGGER.warning(
                "Back-pressure rejected memory write to %s tier: %s",
                tier_name,
                exc,
            )
            raise
        except MemoryCapacityError as exc:
            LOGGER.warning(
                "Rejected memory write to %s tier due to capacity limits: %s",
                tier_name,
                exc,
            )
            raise
        except asyncio.TimeoutError as exc:
            LOGGER.exception(
                "Timed out storing memory in %s tier after watchdog enforcement",
                tier_name,
            )
            raise MemoryManagerOperationError(
                f"Timed out storing memory in {tier_name} tier"
            ) from exc
        except Exception as exc:  # noqa: BLE001
            LOGGER.exception("Failed to add memory to %s tier", tier_name)
            raise MemoryManagerOperationError(
                f"Failed to add memory: {exc}"
            ) from exc

        if memory_id is None:
            raise MemoryManagerOperationError(
                f"Failed to store memory in {tier_name} tier"
            )
        return str(memory_id)

    async def _maybe_prime_working_memory(
        self,
        memory_id: str,
        tier_name: str,
        importance: float,
        tier: Any,
    ) -> None:
        """Populate working memory with high-importance memories."""

        if importance <= 0.7 or not self._current_context:
            return

        memory_data = await tier.retrieve(memory_id)
        if not memory_data:
            return

        memory_item = self._coerce_memory_item(memory_data)
        self._working_memory.add_item(
            WorkingMemoryItem(
                memory=memory_item,
                source_tier=tier_name,
                relevance=0.9,
            )
        )

    async def _audit_creation(
        self,
        serialized_memory: Dict[str, Any],
        memory_id: str,
        tier_name: str,
    ) -> None:
        """Record the creation event with the audit trail."""

        LOGGER.debug("Added memory %s to %s tier", memory_id, tier_name)
        await self._audit_trail.record_creation(
            {**serialized_memory, "id": str(memory_id)},
            tier=tier_name,
        )


__all__ = ["MemoryManagerAddMixin"]
