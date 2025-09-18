"""Audit logging and event emission helpers for the memory manager.

This module centralises the logic responsible for producing structured,
redacted audit logs alongside security focused memory events.  The helpers
ensure that sensitive content never leaks through log statements while still
providing downstream systems with the contextual metadata required for
observability, compliance, and adaptive controls.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Awaitable, Callable, Iterable, Mapping, MutableMapping

from neuroca.core.events.handlers import event_bus
from neuroca.core.events.idempotency import (
    EventIdempotencyFilter,
    deterministic_event_id,
    event_fingerprint,
)
from neuroca.core.events.memory import (
    MemoryConsolidatedEvent,
    MemoryCreatedEvent,
    MemoryEvent,
    MemoryType as EventMemoryType,
)

from neuroca.memory.manager.scoping import MemoryRetrievalScope
from neuroca.memory.models.memory_item import MemoryContent, MemoryItem, MemoryMetadata


EventPublisher = Callable[[MemoryEvent], Awaitable[Any]]


class MemoryLogSanitizer:
    """Provide redaction helpers for logging and event payloads."""

    _MAX_LISTED_KEYS = 10

    def __init__(self, placeholder: str = "[REDACTED]") -> None:
        self._placeholder = placeholder

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def summarize_memory(
        self,
        memory: Mapping[str, Any] | MemoryItem,
        *,
        tier: str | None = None,
    ) -> dict[str, Any]:
        """Return a sanitized summary for ``memory`` suitable for logging."""

        memory_dict = self._coerce_memory_dict(memory)
        metadata = self._coerce_metadata_dict(memory_dict.get("metadata"))
        content = self._coerce_content_dict(memory_dict.get("content"))

        metadata_snapshot = self._summarize_metadata(metadata)
        content_snapshot = self._summarize_content(content)

        summary: dict[str, Any] = {
            "id": self.extract_id(memory_dict),
            "tier": (tier or metadata.get("tier") or metadata_snapshot.get("tier")),
            "content_snapshot": content_snapshot,
            "metadata_snapshot": metadata_snapshot,
        }

        summary["summary_length"] = self._safe_length(memory_dict.get("summary"))
        summary["embedding_dimensions"] = metadata.get("embedding_dimensions")
        return summary

    def summarize_scope(
        self, scope: MemoryRetrievalScope | None
    ) -> dict[str, Any] | None:
        """Return a sanitized representation of ``scope``."""

        if scope is None:
            return None

        return {
            "principal_id": scope.principal_id,
            "user_id": scope.user_id,
            "session_id": scope.session_id,
            "roles": sorted(scope.roles) if scope.roles else [],
            "allow_admin": scope.allow_admin,
            "allowed_user_ids": len(scope.allowed_user_ids),
            "allowed_session_ids": len(scope.allowed_session_ids),
        }

    def extract_id(self, memory: Mapping[str, Any] | MemoryItem) -> str | None:
        """Return the identifier for ``memory`` when present."""

        memory_dict = self._coerce_memory_dict(memory)
        candidate = memory_dict.get("id")
        return str(candidate) if candidate is not None else None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _coerce_memory_dict(
        self, memory: Mapping[str, Any] | MemoryItem | None
    ) -> dict[str, Any]:
        if isinstance(memory, MemoryItem):
            try:
                return memory.model_dump()
            except Exception:  # pragma: no cover - defensive conversion
                return memory.dict()

        if isinstance(memory, Mapping):
            return dict(memory)

        return {}

    def _coerce_metadata_dict(
        self, metadata: Mapping[str, Any] | MemoryMetadata | None
    ) -> dict[str, Any]:
        if isinstance(metadata, MemoryMetadata):
            try:
                return metadata.model_dump()
            except Exception:  # pragma: no cover
                return metadata.dict()

        if isinstance(metadata, Mapping):
            return dict(metadata)

        return {}

    def _coerce_content_dict(
        self, content: Mapping[str, Any] | MemoryContent | None
    ) -> dict[str, Any]:
        if isinstance(content, MemoryContent):
            try:
                return content.model_dump()
            except Exception:  # pragma: no cover
                return content.dict()

        if isinstance(content, Mapping):
            return dict(content)

        return {}

    def _safe_length(self, value: Any) -> int:
        if isinstance(value, str):
            return len(value)
        if isinstance(value, (list, tuple, set)):
            return len(value)
        if isinstance(value, Mapping):
            return len(value)
        return 0

    def _summarize_content(self, content: Mapping[str, Any]) -> dict[str, Any]:
        summary: dict[str, Any] = {"has_content": bool(content)}

        text = content.get("text")
        if isinstance(text, str):
            summary["has_text"] = bool(text.strip())
            summary["text_length"] = len(text)
        elif text is not None:
            summary["text_type"] = type(text).__name__

        summary_text = content.get("summary")
        if isinstance(summary_text, str):
            summary["has_summary"] = bool(summary_text.strip())
            summary["summary_length"] = len(summary_text)
        elif summary_text is not None:
            summary["summary_type"] = type(summary_text).__name__

        json_data = content.get("json_data")
        if isinstance(json_data, Mapping):
            summary["json_field_count"] = len(json_data)
            summary["json_fields"] = self._limited_sorted_keys(json_data.keys())
        elif json_data is not None:
            summary["json_type"] = type(json_data).__name__

        raw_content = content.get("raw_content")
        if isinstance(raw_content, str):
            summary["raw_length"] = len(raw_content)
        elif raw_content is not None:
            summary["raw_type"] = type(raw_content).__name__

        if content.get("content_type"):
            summary["content_type"] = str(content.get("content_type"))
        if content.get("language"):
            summary["language"] = str(content.get("language"))

        return summary

    def _summarize_metadata(self, metadata: Mapping[str, Any]) -> dict[str, Any]:
        summary: dict[str, Any] = {}

        for key in (
            "tier",
            "status",
            "importance",
            "strength",
            "source",
            "user_id",
            "session_id",
            "tenant_id",
            "embedding_model",
            "embedding_dimensions",
        ):
            value = metadata.get(key)
            if value is None:
                continue
            if isinstance(value, (int, float)):
                summary[key] = value
            else:
                summary[key] = str(value)

        for key in ("created_at", "updated_at", "last_accessed"):
            value = metadata.get(key)
            if isinstance(value, datetime):
                summary[key] = value.isoformat()
            elif isinstance(value, str):
                summary[key] = value

        tags = metadata.get("tags")
        if isinstance(tags, Mapping):
            summary["tags"] = {
                "count": len(tags),
                "keys": self._limited_sorted_keys(tags.keys()),
            }

        shared_with = metadata.get("shared_with")
        if isinstance(shared_with, Iterable) and not isinstance(shared_with, (str, bytes)):
            summary["shared_with_count"] = len(
                [item for item in shared_with if item]
            )

        additional = metadata.get("additional_metadata")
        if isinstance(additional, Mapping):
            summary["additional_metadata_keys"] = self._limited_sorted_keys(
                additional.keys()
            )
            summary["additional_metadata_count"] = len(additional)

        return summary

    def _limited_sorted_keys(self, keys: Iterable[Any]) -> list[str]:
        normalized = [str(key) for key in keys if key is not None]
        normalized.sort()
        return normalized[: self._MAX_LISTED_KEYS]


class MemoryAuditTrail:
    """Emit sanitized audit logs and structured memory events."""

    _TIER_TO_MEMORY_TYPE = {
        "stm": EventMemoryType.WORKING,
        "mtm": EventMemoryType.EPISODIC,
        "ltm": EventMemoryType.SEMANTIC,
    }

    def __init__(
        self,
        *,
        log: logging.Logger | None = None,
        publisher: EventPublisher | None = None,
        sanitizer: MemoryLogSanitizer | None = None,
        idempotency_filter: EventIdempotencyFilter | None = None,
    ) -> None:
        self._log = log or logging.getLogger(__name__).getChild("audit")
        self._publisher = publisher or event_bus.publish
        self._sanitizer = sanitizer or MemoryLogSanitizer()
        self._idempotency = idempotency_filter or EventIdempotencyFilter()

    async def record_creation(
        self,
        memory: Mapping[str, Any] | MemoryItem,
        *,
        tier: str,
        scope: MemoryRetrievalScope | None = None,
    ) -> None:
        """Log and emit a sanitized MemoryCreated event."""

        summary = self._sanitizer.summarize_memory(memory, tier=tier)
        scope_summary = self._sanitizer.summarize_scope(scope)
        await self._log_and_emit(
            action="memory.created",
            summary=summary,
            scope_summary=scope_summary,
            event_factory=lambda: self._build_created_event(
                summary=summary,
                tier=tier,
                scope_summary=scope_summary,
            ),
        )

    async def record_consolidation(
        self,
        memory: Mapping[str, Any] | MemoryItem,
        *,
        source_tier: str,
        target_tier: str,
        new_memory_id: str | None = None,
    ) -> None:
        """Log and emit a sanitized MemoryConsolidated event."""

        summary = self._sanitizer.summarize_memory(memory, tier=target_tier)
        source_id = self._sanitizer.extract_id(memory)

        await self._log_and_emit(
            action="memory.consolidated",
            summary=summary,
            scope_summary=None,
            event_factory=lambda: self._build_consolidated_event(
                summary=summary,
                source_tier=source_tier,
                target_tier=target_tier,
                source_id=source_id,
                new_memory_id=new_memory_id,
            ),
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _log_and_emit(
        self,
        *,
        action: str,
        summary: dict[str, Any],
        scope_summary: dict[str, Any] | None,
        event_factory: Callable[[], MemoryEvent | None],
    ) -> None:
        try:
            event = event_factory()
        except Exception:  # pragma: no cover - defensive guard
            self._log.debug("Failed to build %s event", action, exc_info=True)
            return

        if event is None:
            return

        fingerprint = event_fingerprint(event)
        if not self._idempotency.should_emit(fingerprint):
            self._log.debug("Skipping duplicate %s event", action)
            return

        event.id = deterministic_event_id(fingerprint)

        payload: dict[str, Any] = {"action": action, **summary}
        if scope_summary:
            payload["scope"] = scope_summary

        self._log.info("%s | %s", action, self._serialize(payload))

        try:
            await self._publisher(event)
        except Exception:  # pragma: no cover - downstream transport guard
            self._log.warning("Failed to publish %s event", action, exc_info=True)

    def _build_created_event(
        self,
        *,
        summary: dict[str, Any],
        tier: str,
        scope_summary: dict[str, Any] | None,
    ) -> MemoryCreatedEvent:
        metadata = dict(summary.get("metadata_snapshot", {}))
        metadata["tier"] = tier
        if scope_summary:
            metadata["scope"] = scope_summary

        content = summary.get("content_snapshot", {})

        memory_id = summary.get("id") or ""
        if not memory_id:
            memory_id = "unknown"

        return MemoryCreatedEvent(
            memory_id=memory_id,
            memory_type=self._resolve_memory_type(tier),
            content=content,
            metadata=metadata,
        )

    def _build_consolidated_event(
        self,
        *,
        summary: dict[str, Any],
        source_tier: str,
        target_tier: str,
        source_id: str | None,
        new_memory_id: str | None,
    ) -> MemoryConsolidatedEvent:
        metadata = dict(summary.get("metadata_snapshot", {}))
        metadata.update(
            {
                "source_tier": source_tier,
                "target_tier": target_tier,
            }
        )
        if source_id:
            metadata["source_memory_id"] = source_id

        content = summary.get("content_snapshot", {})
        memory_id = new_memory_id or summary.get("id") or "unknown"

        return MemoryConsolidatedEvent(
            memory_id=memory_id,
            memory_type=self._resolve_memory_type(target_tier),
            source_memory_type=self._resolve_memory_type(source_tier),
            target_memory_type=self._resolve_memory_type(target_tier),
            content=content,
            metadata=metadata,
        )

    def _resolve_memory_type(self, tier: str) -> EventMemoryType:
        normalized = (tier or "").lower()
        return self._TIER_TO_MEMORY_TYPE.get(normalized, EventMemoryType.EPISODIC)

    def _serialize(self, payload: MutableMapping[str, Any]) -> str:
        return json.dumps(payload, sort_keys=True, default=self._json_default)

    def _json_default(self, value: Any) -> Any:
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, set):
            return sorted(value)
        return str(value)


__all__ = ["MemoryAuditTrail", "MemoryLogSanitizer"]

