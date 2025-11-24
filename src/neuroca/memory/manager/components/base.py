"""Base configuration and helpers for the asynchronous memory manager."""

from __future__ import annotations

import asyncio
import logging
from types import SimpleNamespace
from typing import Any, Dict, Iterable, Optional

from neuroca.core.enums import MemoryTier
from neuroca.memory.backends import BackendType
from neuroca.memory.manager.audit import MemoryAuditTrail
from neuroca.memory.manager.backpressure import BackpressureController
from neuroca.memory.manager.capacity_pressure import TierCapacityPressureAdapter
from neuroca.memory.manager.circuit_breaker import MaintenanceCircuitBreaker
from neuroca.memory.manager.consolidation_guard import ConsolidationInFlightGuard
from neuroca.memory.manager.consolidation_pipeline import TransactionalConsolidationPipeline
from neuroca.memory.manager.drift_monitor import EmbeddingDriftMonitor
from neuroca.memory.manager.events import MaintenanceEventPublisher
from neuroca.memory.manager.metrics import MemoryMetricsPublisher
from neuroca.memory.manager.quality import MemoryQualityAnalyzer
from neuroca.memory.manager.resource_limits import ResourceLimitWatchdog
from neuroca.memory.manager.sanitization import MemorySanitizer
from neuroca.memory.models.memory_item import MemoryItem
from neuroca.memory.models.working_memory import WorkingMemoryBuffer
from neuroca.memory.interfaces.memory_manager import MemoryManagerInterface

LOGGER = logging.getLogger("neuroca.memory.manager")


class MemoryManagerBase(MemoryManagerInterface):
    """Provide shared configuration and compatibility helpers for MemoryManager."""

    logger = LOGGER

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        backend_type: Optional[BackendType] = None,
        backend_config: Optional[Dict[str, Any]] = None,
        *,
        stm_storage_type: Optional[BackendType] = None,
        mtm_storage_type: Optional[BackendType] = None,
        ltm_storage_type: Optional[BackendType] = None,
        vector_storage_type: Optional[BackendType] = None,
        stm: Optional[Any] = None,
        mtm: Optional[Any] = None,
        ltm: Optional[Any] = None,
        working_buffer_size: int = 20,
        embedding_dimension: int = 768,
    ) -> None:
        """Initialise shared manager state and supporting services."""

        self._config = config or {}
        self._backend_config = backend_config or {}

        self._stm_storage_type = stm_storage_type or backend_type or BackendType.MEMORY
        self._mtm_storage_type = mtm_storage_type or backend_type or BackendType.MEMORY
        self._ltm_storage_type = ltm_storage_type or backend_type or BackendType.MEMORY
        self._vector_storage_type = vector_storage_type or backend_type or BackendType.MEMORY

        self._stm_instance = stm
        self._mtm_instance = mtm
        self._ltm_instance = ltm

        self._working_buffer_size = working_buffer_size
        self._embedding_dimension = embedding_dimension

        self._stm_config = self._config.get("stm", {})
        self._mtm_config = self._config.get("mtm", {})
        self._ltm_config = self._config.get("ltm", {})

        self._backend_type = backend_type

        self._stm = None
        self._mtm = None
        self._ltm = None
        self._ltm_retrieval_cache: dict[str, Any] = {}

        self._working_memory = WorkingMemoryBuffer()

        self._initialized = False

        self._maintenance_task = None
        self._maintenance_orchestrator = None
        self._shutdown_event = asyncio.Event()
        drain_timeout = self._config.get("shutdown_drain_timeout_seconds", 30.0)
        try:
            self._shutdown_drain_timeout = max(0.0, float(drain_timeout))
        except (TypeError, ValueError):
            self._shutdown_drain_timeout = 30.0

        self._current_context = {}
        self._current_context_embedding = None

        self._maintenance_interval = self._config.get("maintenance_interval", 3600)
        if self._maintenance_interval and self._maintenance_interval > 0:
            default_retry = max(5.0, float(self._maintenance_interval) / 4.0)
        else:
            default_retry = 60.0
        try:
            configured_retry = float(
                self._config.get("maintenance_retry_interval_seconds", default_retry)
            )
        except (TypeError, ValueError):
            configured_retry = default_retry
        self._maintenance_retry_interval = max(5.0, configured_retry)

        self._consolidation_pipeline = TransactionalConsolidationPipeline(
            log=LOGGER.getChild("manager.pipeline")
        )

        dedupe_window = self._config.get("consolidation_dedupe_window_seconds", 30.0)
        try:
            dedupe_window_value = float(dedupe_window)
        except (TypeError, ValueError):
            dedupe_window_value = 30.0

        self._consolidation_guard = ConsolidationInFlightGuard(
            dedupe_window_seconds=dedupe_window_value
        )

        resource_limits_config = self._config.get("resource_limits")
        if not isinstance(resource_limits_config, dict):
            resource_limits_config = {}
        self._resource_watchdog = ResourceLimitWatchdog.from_config(
            resource_limits_config,
            log=LOGGER.getChild("manager.resources"),
        )

        backpressure_config = self._config.get("backpressure")
        if not isinstance(backpressure_config, dict):
            backpressure_config = {}
        self._backpressure = BackpressureController.from_config(
            backpressure_config,
            log=LOGGER.getChild("manager.backpressure"),
        )

        self._capacity_adapter = TierCapacityPressureAdapter(
            log=LOGGER.getChild("manager.capacity")
        )

        self._sanitizer = MemorySanitizer(
            log=LOGGER.getChild("manager.sanitizer")
        )
        self._audit_trail = MemoryAuditTrail(
            log=LOGGER.getChild("manager.audit")
        )
        quality_config = self._config.get("quality_monitoring")
        if not isinstance(quality_config, dict):
            quality_config = {}
        self._quality_analyzer = MemoryQualityAnalyzer.from_config(
            quality_config,
            log=LOGGER.getChild("manager.quality"),
        )
        self._quality_state = SimpleNamespace(
            last_report=None,
            last_evaluated_at=None,
        )

        monitoring_config = self._config.get("monitoring")
        metrics_config: dict[str, Any]
        events_config: dict[str, Any]
        if isinstance(monitoring_config, dict):
            metrics_candidate = monitoring_config.get("metrics")
            metrics_config = metrics_candidate if isinstance(metrics_candidate, dict) else {}
            events_candidate = monitoring_config.get("events")
            events_config = events_candidate if isinstance(events_candidate, dict) else {}
        else:
            metrics_config = {}
            events_config = {}
        self._metrics = MemoryMetricsPublisher(
            metrics_config,
            log=LOGGER.getChild("manager.metrics"),
        )
        self._event_publisher = MaintenanceEventPublisher(
            events_config,
            log=LOGGER.getChild("manager.events"),
        )
        drift_config = self._config.get("drift_monitoring")
        if not isinstance(drift_config, dict):
            drift_config = {}
        self._drift_monitor = EmbeddingDriftMonitor.from_config(
            drift_config,
            log=LOGGER.getChild("manager.drift"),
        )
        self._drift_monitor.configure(
            vector_backend=None,
            metrics=self._metrics,
            event_publisher=self._event_publisher,
            quality_provider=self.evaluate_memory_quality,
        )
        self._drift_state = SimpleNamespace(last_report=None, last_checked_at=None)

        breaker_defaults: dict[str, Any] = {
            "queued_backlog_threshold": 64,
            "failure_threshold": 3,
            "cooldown_seconds": 180.0,
        }
        maintenance_section = self._config.get("maintenance")
        breaker_config: dict[str, Any] | None = None
        if isinstance(maintenance_section, dict):
            candidate = maintenance_section.get("circuit_breaker")
            if isinstance(candidate, dict):
                breaker_config = dict(candidate)
            elif candidate is False:
                breaker_config = {"enabled": False}
        if breaker_config is None:
            breaker_config = breaker_defaults
        else:
            merged = dict(breaker_defaults)
            merged |= breaker_config
            breaker_config = merged

        self._consolidation_breaker = MaintenanceCircuitBreaker.from_config(
            breaker_config,
            log=LOGGER.getChild("manager.circuit_breaker"),
        )

    @staticmethod
    async def _delete_if_supported(tier: Any, memory_id: Any, *, context: str) -> None:
        """Delete ``memory_id`` from ``tier`` if the tier exposes a delete method."""

        if not memory_id:
            return

        delete_handler = getattr(tier, "delete", None)
        if delete_handler is None:
            return

        try:
            await delete_handler(memory_id)
        except Exception:  # noqa: BLE001
            LOGGER.exception("Rollback delete failed for %s during %s", memory_id, context)

    @staticmethod
    def _normalize_tier_name(tier: Any | None) -> Optional[str]:
        """Normalize tier inputs originating from legacy call sites."""

        if tier is None:
            return None
        if isinstance(tier, MemoryTier):
            return tier.storage_key
        try:
            return MemoryTier.from_string(str(tier)).storage_key
        except ValueError:
            return str(tier).strip().lower()

    @staticmethod
    def _merge_metadata(
        metadata: Any | None,
        *,
        emotional_salience: float | None,
    ) -> dict[str, Any]:
        """Return a metadata dictionary honoring historical call patterns."""

        base: dict[str, Any] = {}
        if isinstance(metadata, dict):
            base |= metadata
        elif metadata is not None:
            base["legacy_metadata"] = metadata

        if emotional_salience is not None and "emotional_salience" not in base:
            base["emotional_salience"] = emotional_salience

        return base

    @staticmethod
    def _extract_content_payload(content: Any) -> Any:
        """Derive the legacy-facing content payload from tier search results."""

        if isinstance(content, dict):
            for key in ("data", "raw_content", "json_data"):
                if content.get(key) is not None:
                    return content[key]
            text = content.get("text")
            if text is not None:
                return text
            summary = content.get("summary")
            if summary is not None:
                return summary
        return content

    @classmethod
    def _wrap_search_results(cls, results: Iterable[Any] | None) -> list[Any]:
        """Coerce search results into legacy-compatible objects."""

        if not results:
            return []

        wrapped: list[Any] = []
        for item in results:
            if isinstance(item, MemoryItem):
                wrapped.append(
                    SimpleNamespace(
                        content=cls._extract_content_payload(item.content.model_dump()),
                        metadata=item.metadata.model_dump(),
                        tier=item.metadata.tier,
                        relevance=item.metadata.relevance,
                        raw=item,
                        id=getattr(item, "id", None),
                    )
                )
                continue

            if hasattr(item, "content") and hasattr(item, "metadata"):
                wrapped.append(item)
                continue

            if isinstance(item, dict):
                metadata = item.get("metadata")
                if not isinstance(metadata, dict):
                    metadata = {} if metadata is None else {"legacy_metadata": metadata}
                wrapped.append(
                    SimpleNamespace(
                        content=cls._extract_content_payload(item.get("content")),
                        metadata=metadata,
                        tier=item.get("tier") or metadata.get("tier"),
                        relevance=item.get("_relevance") or metadata.get("relevance"),
                        raw=item,
                        id=item.get("id") or metadata.get("id"),
                    )
                )
                continue

            wrapped.append(item)

        return wrapped


__all__ = ["LOGGER", "MemoryManagerBase"]
