"""Visibility and access-control helpers for memory retrieval."""

from __future__ import annotations

from typing import Any, Mapping, Tuple

from neuroca.core.exceptions import MemoryAccessDeniedError
from neuroca.memory.manager.scoping import MemoryRetrievalScope
from neuroca.memory.models.memory_item import MemoryItem, MemoryMetadata


class MemoryManagerVisibilityMixin:
    """Ensure scope-aware access to stored memories."""

    def _normalize_scope(
        self, scope: MemoryRetrievalScope | None
    ) -> MemoryRetrievalScope:
        """Return a usable scope instance."""

        return scope or MemoryRetrievalScope.system()

    def _extract_metadata_dict(self, memory: Any) -> dict[str, Any]:
        """Return a metadata dictionary from ``memory``."""

        if isinstance(memory, MemoryItem):
            try:
                metadata = memory.metadata.model_dump()
            except Exception:  # noqa: BLE001
                metadata = {}
            return metadata if isinstance(metadata, dict) else {}

        if isinstance(memory, Mapping):
            metadata = memory.get("metadata")
            if isinstance(metadata, MemoryMetadata):
                try:
                    metadata = metadata.model_dump()
                except Exception:  # noqa: BLE001
                    metadata = {}
            return metadata if isinstance(metadata, dict) else {}

        return {}

    def _partition_metadata_fields(
        self, metadata: Mapping[str, Any]
    ) -> Tuple[dict[str, Any], dict[str, Any]]:
        """Split metadata into recognised and additional mappings."""

        allowed = {
            key
            for key in MemoryMetadata.model_fields.keys()
            if key not in {"tags", "additional_metadata"}
        }

        recognised: dict[str, Any] = {}
        extras: dict[str, Any] = {}

        for key, value in metadata.items():
            if key in allowed:
                recognised[key] = value
            else:
                extras[key] = value

        return recognised, extras

    def _assert_memory_access(
        self,
        memory_id: str,
        metadata: Mapping[str, Any],
        scope: MemoryRetrievalScope,
        operation: str,
    ) -> None:
        """Raise when ``metadata`` falls outside ``scope``."""

        if scope.allows_metadata(metadata):
            return

        principal = scope.principal_id or "unknown"
        raise MemoryAccessDeniedError(memory_id, principal, operation)

    def _is_memory_visible(
        self,
        memory: Any,
        scope: MemoryRetrievalScope,
    ) -> bool:
        """Return True when ``memory`` is accessible within ``scope``."""

        metadata = self._extract_metadata_dict(memory)
        return scope.allows_metadata(metadata)


__all__ = ["MemoryManagerVisibilityMixin"]
