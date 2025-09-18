"""Structured event helpers for maintenance and consolidation workflows."""

from __future__ import annotations

import inspect
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Mapping, Sequence

from neuroca.core.events.base import BaseEvent, EventPriority, EventType
from neuroca.core.events.idempotency import (
    EventIdempotencyFilter,
    deterministic_event_id,
    event_fingerprint,
)
from neuroca.core.events.handlers import event_bus

EventPublisher = Callable[[BaseEvent], Awaitable[Any] | Any]


@dataclass(kw_only=True)
class MaintenanceCycleEvent(BaseEvent):
    """Event emitted when a maintenance cycle changes state."""

    cycle_id: str
    triggered_by: str
    status: str
    duration_seconds: float | None = None
    errors: tuple[str, ...] = field(default_factory=tuple)
    consolidation_summary: dict[str, Any] = field(default_factory=dict)
    decay_summary: dict[str, Any] = field(default_factory=dict)
    cleanup_summary: dict[str, Any] = field(default_factory=dict)
    quality_summary: dict[str, Any] = field(default_factory=dict)
    drift_summary: dict[str, Any] = field(default_factory=dict)
    telemetry_snapshot: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:  # pragma: no cover - simple field coercion
        super().__post_init__()
        self.event_type = EventType.SYSTEM
        normalized_status = str(self.status).strip().lower() or "unknown"
        self.status = normalized_status
        if normalized_status == "started":
            self.priority = EventPriority.LOW
        elif normalized_status in {"error", "failed"}:
            self.priority = EventPriority.HIGH
        else:
            self.priority = EventPriority.NORMAL

        self.metadata.update(
            {
                "cycle_id": self.cycle_id,
                "triggered_by": self.triggered_by,
                "status": self.status,
            }
        )
        if self.duration_seconds is not None:
            self.metadata["duration_seconds"] = max(0.0, float(self.duration_seconds))
        if self.errors:
            self.metadata["errors"] = list(self.errors)
        if self.consolidation_summary:
            self.metadata["consolidation"] = dict(self.consolidation_summary)
        if self.decay_summary:
            self.metadata["decay"] = dict(self.decay_summary)
        if self.cleanup_summary:
            self.metadata["cleanup"] = dict(self.cleanup_summary)
        if self.quality_summary:
            self.metadata["quality"] = dict(self.quality_summary)
        if self.drift_summary:
            self.metadata["drift"] = dict(self.drift_summary)
        if self.telemetry_snapshot:
            self.metadata["telemetry"] = dict(self.telemetry_snapshot)


@dataclass(kw_only=True)
class ConsolidationOutcomeEvent(BaseEvent):
    """Summarise the result of a single consolidation attempt."""

    memory_id: str
    source_tier: str
    target_tier: str
    status: str
    duration_seconds: float | None
    result_id: str | None = None
    error: str | None = None

    def __post_init__(self) -> None:  # pragma: no cover - simple field coercion
        super().__post_init__()
        self.event_type = EventType.MEMORY
        normalized_status = str(self.status).strip().lower() or "unknown"
        self.status = normalized_status
        if normalized_status in {"error", "failed"}:
            self.priority = EventPriority.HIGH
        elif normalized_status == "success":
            self.priority = EventPriority.NORMAL
        else:
            self.priority = EventPriority.LOW

        self.metadata.update(
            {
                "memory_id": self.memory_id,
                "source_tier": self.source_tier,
                "target_tier": self.target_tier,
                "status": self.status,
            }
        )
        if self.duration_seconds is not None:
            self.metadata["duration_seconds"] = max(0.0, float(self.duration_seconds))
        if self.result_id:
            self.metadata["result_id"] = self.result_id
        if self.error:
            self.metadata["error"] = self.error


@dataclass(kw_only=True)
class EmbeddingDriftEvent(BaseEvent):
    """Structured notification emitted when embedding drift is detected."""

    alerts: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    quality_score: float | None = None
    quality_delta: float | None = None
    max_drift: float | None = None
    drifted_ids: tuple[str, ...] = field(default_factory=tuple)
    quality_summary: dict[str, Any] = field(default_factory=dict)
    integrity_summary: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:  # pragma: no cover - simple coercion
        super().__post_init__()
        self.event_type = EventType.SYSTEM
        severity = "info"
        if self.alerts:
            first = self.alerts[0]
            severity = str(first.get("severity", severity))

        if severity == "critical":
            self.priority = EventPriority.HIGH
        elif severity == "warning":
            self.priority = EventPriority.NORMAL
        else:
            self.priority = EventPriority.LOW

        if self.alerts:
            self.metadata["alerts"] = [dict(alert) for alert in self.alerts]
        if self.quality_score is not None:
            self.metadata["quality_score"] = float(self.quality_score)
        if self.quality_delta is not None:
            self.metadata["quality_delta"] = float(self.quality_delta)
        if self.max_drift is not None:
            self.metadata["max_drift"] = float(self.max_drift)
        if self.drifted_ids:
            self.metadata["drifted_ids"] = list(self.drifted_ids)
        if self.quality_summary:
            self.metadata["quality"] = dict(self.quality_summary)
        if self.integrity_summary:
            self.metadata["integrity"] = dict(self.integrity_summary)


class MaintenanceEventPublisher:
    """Publish structured events describing maintenance activity."""

    def __init__(
        self,
        config: Mapping[str, Any] | None = None,
        *,
        log: logging.Logger | None = None,
        publisher: EventPublisher | None = None,
    ) -> None:
        self._log = log or logging.getLogger(__name__).getChild("events")
        cfg = dict(config or {})
        self._enabled = bool(cfg.get("enabled", True))
        self._publisher: EventPublisher = publisher or event_bus.publish
        self._idempotency_enabled = bool(cfg.get("dedupe_enabled", True))
        ttl = self._coerce_float(cfg.get("dedupe_ttl_seconds"), fallback=600.0)
        max_entries = self._coerce_int(cfg.get("dedupe_max_entries"), fallback=2048)
        self._idempotency = EventIdempotencyFilter(
            ttl_seconds=ttl if ttl is not None else 600.0,
            max_entries=max_entries if max_entries is not None else 2048,
        )

    @property
    def enabled(self) -> bool:
        """Return ``True`` when structured event emission is active."""

        return self._enabled

    async def cycle_started(self, *, cycle_id: str, triggered_by: str) -> None:
        """Emit a ``started`` event for the given maintenance cycle."""

        if not self.enabled:
            return

        event = MaintenanceCycleEvent(
            cycle_id=cycle_id,
            triggered_by=triggered_by,
            status="started",
            duration_seconds=None,
        )
        await self._publish(event)

    async def cycle_completed(
        self,
        *,
        cycle_id: str,
        triggered_by: str,
        report: Mapping[str, Any],
    ) -> None:
        """Emit a completion event summarising the maintenance cycle."""

        if not self.enabled:
            return

        event = MaintenanceCycleEvent(
            cycle_id=cycle_id,
            triggered_by=triggered_by,
            status=self._coerce_status(report.get("status"), fallback="ok"),
            duration_seconds=self._coerce_float(report.get("duration_seconds")),
            errors=self._coerce_errors(report.get("errors")),
            consolidation_summary=self._coerce_mapping(report.get("consolidation")),
            decay_summary=self._coerce_mapping(report.get("decay")),
            cleanup_summary=self._coerce_mapping(report.get("cleanup")),
            quality_summary=self._coerce_mapping(report.get("quality")),
            drift_summary=self._coerce_mapping(report.get("drift")),
            telemetry_snapshot=self._coerce_mapping(report.get("telemetry")),
        )
        await self._publish(event)

    async def consolidation_completed(
        self,
        *,
        memory_id: str,
        source_tier: str,
        target_tier: str,
        status: str,
        duration_seconds: float | None,
        result_id: str | None,
        error: str | None = None,
    ) -> None:
        """Emit a consolidation outcome event."""

        if not self.enabled:
            return

        event = ConsolidationOutcomeEvent(
            memory_id=memory_id,
            source_tier=source_tier,
            target_tier=target_tier,
            status=self._coerce_status(status, fallback="unknown"),
            duration_seconds=self._coerce_float(duration_seconds),
            result_id=result_id,
            error=str(error) if error else None,
        )
        await self._publish(event)

    async def embedding_drift_detected(
        self,
        *,
        alerts: Sequence[Mapping[str, Any]],
        quality_summary: Mapping[str, Any],
        integrity_summary: Mapping[str, Any],
        quality_score: float | None,
        quality_delta: float | None,
        max_drift: float | None,
    ) -> None:
        """Emit an event describing detected embedding drift."""

        if not self.enabled:
            return

        event = EmbeddingDriftEvent(
            alerts=tuple(dict(alert) for alert in alerts),
            quality_score=quality_score,
            quality_delta=quality_delta,
            max_drift=max_drift,
            drifted_ids=tuple(
                str(item)
                for alert in alerts
                for item in self._coerce_sequence(alert.get("drifted_ids"))
            ),
            quality_summary=self._coerce_mapping(quality_summary),
            integrity_summary=self._coerce_mapping(integrity_summary),
        )
        await self._publish(event)

    async def _publish(self, event: BaseEvent) -> None:
        try:
            fingerprint = event_fingerprint(event)
            if self._idempotency_enabled and not self._idempotency.should_emit(fingerprint):
                self._log.debug(
                    "Skipping duplicate %s event", event.__class__.__name__
                )
                return

            event.id = deterministic_event_id(fingerprint)
            result = self._publisher(event)
            if inspect.isawaitable(result):
                await result
        except Exception:  # pragma: no cover - downstream transport guard
            self._log.debug(
                "Failed to publish %s", event.__class__.__name__, exc_info=True
            )

    @staticmethod
    def new_cycle_id() -> str:
        """Return a unique maintenance cycle identifier."""

        return str(uuid.uuid4())

    @staticmethod
    def _coerce_float(value: Any, fallback: float | None = None) -> float | None:
        if value is None:
            return fallback
        try:
            return float(value)
        except (TypeError, ValueError):
            return fallback

    @staticmethod
    def _coerce_status(value: Any, *, fallback: str) -> str:
        candidate = str(value).strip().lower() if value is not None else ""
        return candidate or fallback

    @staticmethod
    def _coerce_int(value: Any, *, fallback: int | None = None) -> int | None:
        if value is None:
            return fallback
        try:
            coerced = int(value)
        except (TypeError, ValueError):
            return fallback
        return coerced if coerced > 0 else fallback

    @staticmethod
    def _coerce_mapping(value: Any) -> dict[str, Any]:
        if isinstance(value, Mapping):
            return {str(key): value[key] for key in value}
        return {}

    @staticmethod
    def _coerce_errors(value: Any) -> tuple[str, ...]:
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            return tuple(str(item) for item in value if item is not None)
        if value is None:
            return tuple()
        return (str(value),)

    @staticmethod
    def _coerce_sequence(value: Any) -> tuple[Any, ...]:
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            return tuple(value)
        return tuple()


__all__ = [
    "ConsolidationOutcomeEvent",
    "EmbeddingDriftEvent",
    "MaintenanceCycleEvent",
    "MaintenanceEventPublisher",
]
