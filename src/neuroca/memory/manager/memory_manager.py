"""
Memory Manager Implementation

This module provides the implementation of the Memory Manager, which serves as
the central orchestration layer for the entire memory system, coordinating
operations across all memory tiers (STM, MTM, LTM) and providing a unified API.
"""

import asyncio
import inspect
import logging
import time
from datetime import datetime, timezone
from time import perf_counter
from types import SimpleNamespace
from typing import Any, Awaitable, Callable, Dict, Iterable, List, Mapping, Optional, Union

from neuroca.core.enums import MemoryTier
from neuroca.core.exceptions import MemoryAccessDeniedError, MemoryValidationError
from neuroca.memory.backends import BackendType
from neuroca.memory.exceptions import (
    MemoryBackpressureError,
    MemoryCapacityError,
    MemoryManagerInitializationError,
    MemoryManagerOperationError,
    MemoryNotFoundError,
    InvalidTierError,
)
from neuroca.memory.interfaces.memory_manager import MemoryManagerInterface
from neuroca.memory.manager.audit import MemoryAuditTrail
from neuroca.memory.manager.consolidation_pipeline import (
    ConsolidationSkip,
    ConsolidationTransaction,
    TransactionalConsolidationPipeline,
)
from neuroca.memory.manager.consolidation_guard import (
    ConsolidationInFlightGuard,
)
from neuroca.memory.manager.backpressure import BackpressureController
from neuroca.memory.manager.capacity_pressure import TierCapacityPressureAdapter
from neuroca.memory.manager.circuit_breaker import (
    CircuitBreakerDecision,
    MaintenanceCircuitBreaker,
)
from neuroca.memory.manager.events import MaintenanceEventPublisher
from neuroca.memory.manager.maintenance import MaintenanceOrchestrator
from neuroca.memory.manager.metrics import MemoryMetricsPublisher
from neuroca.memory.manager.resource_limits import ResourceLimitWatchdog
from neuroca.memory.manager.quality import MemoryQualityAnalyzer
from neuroca.memory.manager.sanitization import MemorySanitizer
from neuroca.memory.manager.scoping import MemoryRetrievalScope
from neuroca.memory.manager.drift_monitor import EmbeddingDriftMonitor
from neuroca.memory.models.memory_item import MemoryItem, MemoryContent, MemoryMetadata
from neuroca.memory.models.working_memory import WorkingMemoryBuffer, WorkingMemoryItem
from neuroca.memory.tiers.stm.core import ShortTermMemoryTier
from neuroca.memory.tiers.mtm.core import MediumTermMemoryTier
from neuroca.memory.tiers.ltm.core import LongTermMemoryTier


logger = logging.getLogger(__name__)


class MemoryManager(MemoryManagerInterface):
    """
    Memory Manager Implementation
    
    The Memory Manager serves as the central orchestration layer for the
    memory system, coordinating operations across memory tiers (STM, MTM, LTM)
    and providing a unified API for the entire system.
    
    This class implements the MemoryManagerInterface and provides all the
    functionality described in the interface.
    """
    
    # Tier names
    STM_TIER = "stm"
    MTM_TIER = "mtm"
    LTM_TIER = "ltm"
    
    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        backend_type: Optional[BackendType] = None,
        backend_config: Optional[Dict[str, Any]] = None,
        # Support for tier-specific storage types (new API)
        stm_storage_type: Optional[BackendType] = None,
        mtm_storage_type: Optional[BackendType] = None, 
        ltm_storage_type: Optional[BackendType] = None,
        vector_storage_type: Optional[BackendType] = None,
        # Support for direct tier instances (test API)
        stm: Optional[Any] = None,
        mtm: Optional[Any] = None,
        ltm: Optional[Any] = None,
        # Additional config options
        working_buffer_size: int = 20,
        embedding_dimension: int = 768,
    ):
        """
        Initialize the Memory Manager.
        
        Args:
            config: Configuration dictionary
            backend_type: Type of backend to use for all tiers
            backend_config: Backend configuration
        """
        self._config = config or {}
        self._backend_config = backend_config or {}
        
        # Handle tier-specific storage types (NEW API)
        self._stm_storage_type = stm_storage_type or backend_type or BackendType.MEMORY
        self._mtm_storage_type = mtm_storage_type or backend_type or BackendType.MEMORY
        self._ltm_storage_type = ltm_storage_type or backend_type or BackendType.MEMORY
        self._vector_storage_type = vector_storage_type or backend_type or BackendType.MEMORY
        
        # Handle direct tier instances (TEST API)
        self._stm_instance = stm
        self._mtm_instance = mtm
        self._ltm_instance = ltm
        
        # Additional configuration
        self._working_buffer_size = working_buffer_size
        self._embedding_dimension = embedding_dimension
        
        # Set default tier configurations
        self._stm_config = self._config.get("stm", {})
        self._mtm_config = self._config.get("mtm", {})
        self._ltm_config = self._config.get("ltm", {})
        
        # Legacy support - store for backwards compatibility
        self._backend_type = backend_type
        
        # Initialize tiers to None
        self._stm = None
        self._mtm = None
        self._ltm = None
        
        # Initialize working memory buffer
        self._working_memory = WorkingMemoryBuffer()
        
        # Initialization flag
        self._initialized = False
        
        # Background tasks
        self._maintenance_task = None
        self._maintenance_orchestrator: MaintenanceOrchestrator | None = None
        self._shutdown_event = asyncio.Event()
        drain_timeout = self._config.get("shutdown_drain_timeout_seconds", 30.0)
        try:
            self._shutdown_drain_timeout = max(0.0, float(drain_timeout))
        except (TypeError, ValueError):
            self._shutdown_drain_timeout = 30.0

        # Context related
        self._current_context = {}
        self._current_context_embedding = None

        # Maintenance interval
        self._maintenance_interval = self._config.get("maintenance_interval", 3600)  # Default: 1 hour
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

        # Transactional consolidation pipeline
        self._consolidation_pipeline = TransactionalConsolidationPipeline(
            log=logger.getChild("manager.pipeline")
        )

        dedupe_window = self._config.get(
            "consolidation_dedupe_window_seconds", 30.0
        )
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
            log=logger.getChild("manager.resources"),
        )

        backpressure_config = self._config.get("backpressure")
        if not isinstance(backpressure_config, dict):
            backpressure_config = {}
        self._backpressure = BackpressureController.from_config(
            backpressure_config,
            log=logger.getChild("manager.backpressure"),
        )

        self._capacity_adapter = TierCapacityPressureAdapter(
            log=logger.getChild("manager.capacity")
        )

        self._sanitizer = MemorySanitizer(
            log=logger.getChild("manager.sanitizer")
        )
        self._audit_trail = MemoryAuditTrail(
            log=logger.getChild("manager.audit")
        )
        quality_config = self._config.get("quality_monitoring")
        if not isinstance(quality_config, dict):
            quality_config = {}
        self._quality_analyzer = MemoryQualityAnalyzer.from_config(
            quality_config,
            log=logger.getChild("manager.quality"),
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
            log=logger.getChild("manager.metrics"),
        )
        self._event_publisher = MaintenanceEventPublisher(
            events_config,
            log=logger.getChild("manager.events"),
        )
        drift_config = self._config.get("drift_monitoring")
        if not isinstance(drift_config, dict):
            drift_config = {}
        self._drift_monitor = EmbeddingDriftMonitor.from_config(
            drift_config,
            log=logger.getChild("manager.drift"),
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
            merged.update(breaker_config)
            breaker_config = merged

        self._consolidation_breaker = MaintenanceCircuitBreaker.from_config(
            breaker_config,
            log=logger.getChild("manager.circuit_breaker"),
        )

    # ------------------------------------------------------------------
    # Legacy compatibility helpers
    # ------------------------------------------------------------------

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
            base.update(metadata)
        elif metadata is not None:
            base["legacy_metadata"] = metadata

        if emotional_salience is not None and "emotional_salience" not in base:
            base["emotional_salience"] = emotional_salience

        return base

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
            logger.exception("Rollback delete failed for %s during %s", memory_id, context)

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

    def _legacy_call(
        self,
        coro: Awaitable[Any],
        *,
        transform: Callable[[Any], Any] | None = None,
    ) -> Any:
        """Execute a coroutine while preserving historical synchronous semantics."""

        async def _runner() -> Any:
            result = await coro
            return transform(result) if transform is not None else result

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(_runner())

        task = loop.create_task(_runner())

        def _log_failure(done: asyncio.Future[Any]) -> None:
            if done.cancelled():
                return
            try:
                done.result()
            except Exception:  # noqa: BLE001
                logger.exception("Legacy memory manager compatibility call failed")

        task.add_done_callback(_log_failure)
        return task

    # ------------------------------------------------------------------
    # Legacy public API compatibility
    # ------------------------------------------------------------------

    def store(
        self,
        content: Any,
        *,
        summary: str | None = None,
        importance: float = 0.5,
        metadata: Any | None = None,
        tags: Optional[List[str]] = None,
        memory_type: Any | None = None,
        tier: Any | None = None,
        emotional_salience: float | None = None,
        **kwargs: Any,
    ) -> Any:
        """Store a memory using the legacy synchronous signature."""

        initial_tier = self._normalize_tier_name(tier or memory_type)
        merged_metadata = self._merge_metadata(metadata, emotional_salience=emotional_salience)

        return self._legacy_call(
            self.add_memory(
                content=content,
                summary=summary,
                importance=importance,
                metadata=merged_metadata,
                tags=tags,
                initial_tier=initial_tier,
                **{k: v for k, v in kwargs.items() if k not in {"memory_type", "tier"}},
            )
        )

    def retrieve(
        self,
        *args: Any,
        query: str | None = None,
        memory_id: str | None = None,
        memory_type: Any | None = None,
        tier: Any | None = None,
        limit: int | None = None,
        tags: Optional[List[str]] = None,
        metadata_filters: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Any:
        """Retrieve memories using the historic flexible interface."""

        if args and not query and memory_id is None:
            # Support positional access via ID.
            memory_id = str(args[0])

        if memory_id is not None:
            normalized_tier = self._normalize_tier_name(tier)
            return self._legacy_call(
                self.retrieve_memory(memory_id, tier=normalized_tier),
                transform=lambda result: self._wrap_search_results([result])[0] if result else None,
            )

        normalized_tier = self._normalize_tier_name(tier or memory_type)
        search_kwargs: dict[str, Any] = {
            "query": query or (args[0] if args else None),
            "limit": kwargs.get("top_k", limit),
            "tiers": [normalized_tier] if normalized_tier else None,
        }

        if tags:
            search_kwargs["tags"] = tags
        if metadata_filters:
            search_kwargs["metadata_filters"] = metadata_filters

        return self._legacy_call(
            self.search_memories(**search_kwargs),
            transform=self._wrap_search_results,
        )

    def search(self, query: str | None = None, **kwargs: Any) -> Any:
        """Legacy alias that routed to search APIs."""

        return self.retrieve(query=query, **kwargs)

    def retrieve_relevant(self, query: str, *, tier: Any | None = None, limit: int | None = None, **kwargs: Any) -> Any:
        """Legacy helper used by integration utilities."""

        return self.retrieve(query=query, tier=tier, limit=limit, **kwargs)
    
    async def initialize(self) -> None:
        """
        Initialize the memory manager and all storage components.
        
        This method must be called before any other method.
        
        Raises:
            MemoryManagerInitializationError: If initialization fails
        """
        if self._initialized:
            logger.warning("Memory Manager already initialized")
            return
        
        try:
            logger.info("Initializing Memory Manager")

            self._shutdown_event.clear()

            # Initialize STM tier (use direct instance if provided, otherwise create new)
            logger.debug("Initializing STM tier")
            if self._stm_instance:
                self._stm = self._stm_instance
                if hasattr(self._stm, 'initialize'):
                    await self._stm.initialize()
            else:
                self._stm = ShortTermMemoryTier(
                    backend_type=self._stm_storage_type,
                    backend_config=self._backend_config,
                    config=self._stm_config,
                )
                await self._stm.initialize()
            
            # Initialize MTM tier (use direct instance if provided, otherwise create new)
            logger.debug("Initializing MTM tier")
            if self._mtm_instance:
                self._mtm = self._mtm_instance
                if hasattr(self._mtm, 'initialize'):
                    await self._mtm.initialize()
            else:
                self._mtm = MediumTermMemoryTier(
                    backend_type=self._mtm_storage_type,
                    backend_config=self._backend_config,
                    config=self._mtm_config,
                )
                await self._mtm.initialize()
            
            # Initialize LTM tier (use direct instance if provided, otherwise create new)
            logger.debug("Initializing LTM tier")
            if self._ltm_instance:
                self._ltm = self._ltm_instance
                if hasattr(self._ltm, 'initialize'):
                    await self._ltm.initialize()
            else:
                self._ltm = LongTermMemoryTier(
                    backend_type=self._ltm_storage_type,
                    backend_config=self._backend_config,
                    config=self._ltm_config,
                )
                await self._ltm.initialize()

            await self._refresh_capacity_pressure()
            self._configure_drift_monitor()
            self._ensure_maintenance_orchestrator()

            # Start maintenance task if interval > 0
            if self._maintenance_interval > 0:
                self._start_maintenance_task()

            self._initialized = True
            logger.info("Memory Manager initialization complete")
        except Exception as e:
            logger.exception("Failed to initialize Memory Manager")
            raise MemoryManagerInitializationError(
                f"Failed to initialize Memory Manager: {str(e)}"
            ) from e
    
    async def shutdown(self) -> None:
        """
        Gracefully shut down the memory manager and all storage components.
        
        This method should be called when the memory system is no longer needed
        to ensure all resources are released and pending operations are completed.
        
        Raises:
            MemoryManagerOperationError: If shutdown fails
        """
        if not self._initialized:
            logger.warning("Memory Manager not initialized, nothing to shut down")
            return
        
        try:
            logger.info("Shutting down Memory Manager")

            self._shutdown_event.set()

            drain_timeout = self._shutdown_drain_timeout
            wait_timeout = drain_timeout if drain_timeout > 0 else None

            # Stop maintenance task
            if self._maintenance_task:
                try:
                    if wait_timeout is None:
                        await self._maintenance_task
                    else:
                        await asyncio.wait_for(self._maintenance_task, timeout=wait_timeout)
                except asyncio.TimeoutError:
                    logger.warning(
                        "Timed out waiting for maintenance task to finish; cancelling",
                    )
                    self._maintenance_task.cancel()
                    try:
                        await self._maintenance_task
                    except asyncio.CancelledError:
                        pass
                except asyncio.CancelledError:
                    pass
                except Exception:
                    logger.exception("Maintenance task raised during shutdown")
                finally:
                    self._maintenance_task = None
            self._maintenance_orchestrator = None

            try:
                await self._consolidation_guard.wait_for_all(timeout=wait_timeout)
            except asyncio.TimeoutError:
                logger.warning(
                    "Timed out waiting for in-flight consolidations to finish during shutdown",
                )

            # Shutdown tiers
            if self._stm:
                await self._stm.shutdown()

            if self._mtm:
                await self._mtm.shutdown()
            
            if self._ltm:
                await self._ltm.shutdown()
            
            self._initialized = False
            logger.info("Memory Manager shutdown complete")
        except Exception as e:
            logger.exception("Failed to shut down Memory Manager")
            raise MemoryManagerOperationError(
                f"Failed to shut down Memory Manager: {str(e)}"
            ) from e
    
    def _ensure_initialized(self) -> None:
        """
        Ensure that the Memory Manager is initialized.

        Raises:
            MemoryManagerOperationError: If not initialized
        """
        if not self._initialized:
            raise MemoryManagerOperationError(
                "Memory Manager not initialized. Call initialize() first."
            )

    # ------------------------------------------------------------------
    # Tier accessors
    # ------------------------------------------------------------------

    @property
    def stm_storage(self) -> ShortTermMemoryTier:
        """Return the initialized STM tier instance."""

        self._ensure_initialized()
        if self._stm is None:
            raise MemoryManagerOperationError("STM storage tier not available")
        return self._stm

    @property
    def mtm_storage(self) -> MediumTermMemoryTier:
        """Return the initialized MTM tier instance."""

        self._ensure_initialized()
        if self._mtm is None:
            raise MemoryManagerOperationError("MTM storage tier not available")
        return self._mtm

    @property
    def ltm_storage(self) -> LongTermMemoryTier:
        """Return the initialized LTM tier instance."""

        self._ensure_initialized()
        if self._ltm is None:
            raise MemoryManagerOperationError("LTM storage tier not available")
        return self._ltm

    @property
    def embedding_dimension(self) -> int:
        """Return the configured embedding dimensionality."""

        return self._embedding_dimension

    def get_tier(
        self, tier_name: str
    ) -> ShortTermMemoryTier | MediumTermMemoryTier | LongTermMemoryTier:
        """Public accessor for tier instances using canonical string names."""

        self._ensure_initialized()
        return self._get_tier_by_name(tier_name)

    def _ensure_maintenance_orchestrator(self) -> MaintenanceOrchestrator:
        """Initialise the maintenance orchestrator if it has not been created."""

        if self._maintenance_orchestrator is None:
            telemetry_sink = (
                self._metrics.handle_cycle_report
                if getattr(self, "_metrics", None) and self._metrics.enabled
                else None
            )
            self._maintenance_orchestrator = MaintenanceOrchestrator(
                self,
                min_interval=self._maintenance_retry_interval,
                telemetry_sink=telemetry_sink,
                event_publisher=self._event_publisher,
                log=logger.getChild("manager.maintenance"),
            )
        return self._maintenance_orchestrator

    def _capture_backpressure_snapshot(self) -> dict[str, dict[str, int]] | None:
        """Return a snapshot of back-pressure state used for degradation guards."""

        controller = getattr(self, "_backpressure", None)
        if controller is None:
            return None

        try:
            return controller.snapshot()
        except Exception:  # pragma: no cover - defensive logging
            logger.debug(
                "Failed capturing back-pressure snapshot for circuit breaker",
                exc_info=True,
            )
            return None

    def _evaluate_consolidation_breaker(
        self,
        telemetry: Any,
    ) -> CircuitBreakerDecision | None:
        """Evaluate the consolidation circuit breaker against ``telemetry``."""

        breaker = getattr(self, "_consolidation_breaker", None)
        if breaker is None:
            return None

        snapshot = self._capture_backpressure_snapshot()

        try:
            decision = breaker.evaluate(
                backlog_snapshot=snapshot,
                telemetry=telemetry,
            )
        except Exception:  # pragma: no cover - breaker must not disrupt maintenance
            logger.exception("Maintenance circuit breaker evaluation failed")
            return None

        return decision

    @property
    def consolidation_breaker_status(self) -> dict[str, Any] | None:
        """Expose the breaker status for monitoring surfaces."""

        breaker = getattr(self, "_consolidation_breaker", None)
        if breaker is None:
            return None
        return breaker.status()

    @property
    def last_quality_report(self) -> Optional[Dict[str, Any]]:
        """Return the cached quality report from the most recent evaluation."""

        report = getattr(self._quality_state, "last_report", None)
        if isinstance(report, dict):
            return dict(report)
        return None

    @property
    def last_drift_report(self) -> Optional[Dict[str, Any]]:
        """Return the cached embedding drift evaluation report."""

        report = getattr(self._drift_state, "last_report", None)
        if isinstance(report, dict):
            return dict(report)
        return None

    async def evaluate_memory_quality(self, *, limit: int | None = None) -> Dict[str, Any]:
        """Evaluate LTM quality and return structured metrics."""

        self._ensure_initialized()

        snapshot = await self._collect_ltm_memories(limit=limit)
        report = self._quality_analyzer.evaluate(snapshot)
        self._quality_state.last_report = report
        evaluated_at = report.get("evaluated_at") if isinstance(report, dict) else None
        if isinstance(evaluated_at, str):
            try:
                self._quality_state.last_evaluated_at = datetime.fromisoformat(evaluated_at).timestamp()
            except ValueError:
                self._quality_state.last_evaluated_at = time.time()
        else:
            self._quality_state.last_evaluated_at = time.time()
        return report

    async def detect_embedding_drift(
        self,
        *,
        quality_report: Mapping[str, Any] | None = None,
        force: bool = False,
        sample_size: int | None = None,
    ) -> Dict[str, Any]:
        """Evaluate embedding drift and return a structured summary."""

        self._ensure_initialized()

        monitor = self._drift_monitor
        if monitor is None:
            return {}

        result = await monitor.run_checks(
            quality_report=quality_report,
            force=force,
            sample_size=sample_size,
        )
        if not result:
            return {}

        self._drift_state.last_report = dict(result)
        checked_at = result.get("checked_at")
        if isinstance(checked_at, str):
            try:
                self._drift_state.last_checked_at = datetime.fromisoformat(checked_at).timestamp()
            except ValueError:
                self._drift_state.last_checked_at = time.time()
        else:
            self._drift_state.last_checked_at = time.time()

        return dict(result)

    async def _collect_ltm_memories(self, limit: int | None = None) -> List[Any]:
        """Gather a snapshot of LTM memories for quality analysis."""

        if self._ltm is None:
            return []

        retrieval_methods = ("list_all", "retrieve_all", "list")
        for method_name in retrieval_methods:
            handler = getattr(self._ltm, method_name, None)
            if handler is None:
                continue

            if not callable(handler):
                logger.debug(
                    "Skipping non-callable LTM retrieval handler %s", method_name
                )
                continue

            result: Any = None
            attempted = False
            call_kwargs: List[Dict[str, Any]] = [{}]
            if limit is not None:
                call_kwargs.append({"limit": limit})

            for kwargs in call_kwargs:
                try:
                    result = handler(**kwargs)  # type: ignore[misc]
                except TypeError:
                    continue
                attempted = True
                break

            if result is None and not attempted:
                continue

            try:
                if inspect.isawaitable(result):
                    result = await result
            except Exception:
                logger.exception(
                    "Failed to await LTM retrieval via %s", method_name
                )
                continue

            if result is None:
                continue

            try:
                if hasattr(result, "__aiter__"):
                    collected: List[Any] = []
                    async for item in result:  # type: ignore[assignment]
                        collected.append(item)
                        if limit is not None and len(collected) >= limit:
                            break
                    return collected
                if isinstance(result, dict):
                    sequence = list(result.values())
                elif isinstance(result, (list, tuple, set)):
                    sequence = list(result)
                elif isinstance(result, Iterable) and not isinstance(result, (str, bytes)):
                    sequence = list(result)
                else:
                    continue
            except Exception:
                logger.exception("Failed to coerce LTM snapshot from %s", method_name)
                continue

            if limit is not None:
                return sequence[: limit]
            return sequence

        logger.debug("LTM storage does not expose bulk retrieval; skipping quality analysis")
        return []

    def _configure_drift_monitor(self) -> None:
        backend = None
        if self._ltm is not None:
            backend = getattr(self._ltm, "_backend", None)
        self._drift_monitor.configure(
            vector_backend=backend,
            metrics=self._metrics,
            event_publisher=self._event_publisher,
            quality_provider=self.evaluate_memory_quality,
        )

    def _start_maintenance_task(self) -> None:
        """
        Start the background maintenance task.
        """
        self._ensure_maintenance_orchestrator()
        if self._maintenance_task is None or self._maintenance_task.done():
            self._shutdown_event.clear()
            self._maintenance_task = asyncio.create_task(self._maintenance_loop())
    
    async def _maintenance_loop(self) -> None:
        """
        Background task for periodically running maintenance on all tiers.
        """
        orchestrator = self._ensure_maintenance_orchestrator()
        base_interval = float(self._maintenance_interval)
        if base_interval <= 0:
            base_interval = orchestrator.min_interval

        delay = max(base_interval, orchestrator.min_interval)

        try:
            while not self._shutdown_event.is_set():
                try:
                    await asyncio.wait_for(
                        self._shutdown_event.wait(),
                        timeout=delay,
                    )
                    break
                except asyncio.TimeoutError:
                    pass

                result = await orchestrator.run_cycle(triggered_by="scheduler")
                if result.get("status") == "error":
                    logger.error(
                        "Background maintenance cycle completed with errors: %s",
                        result.get("errors", []),
                    )
                else:
                    logger.debug(
                        "Background maintenance cycle completed successfully"
                    )

                try:
                    await self._refresh_capacity_pressure()
                except Exception:  # noqa: BLE001 - adaptation must not break loop
                    logger.debug(
                        "Capacity pressure refresh failed after maintenance cycle",
                        exc_info=True,
                    )

                if self._shutdown_event.is_set():
                    break

                delay = orchestrator.compute_next_delay(base_interval)
        except asyncio.CancelledError:
            logger.info("Maintenance task cancelled")
            raise
        except Exception as e:
            logger.exception(f"Unexpected error in maintenance loop: {str(e)}")

    def _resolve_tier_capacity(self, tier_name: str, tier: Any) -> int | None:
        """Best effort resolution of capacity for ``tier``."""

        limit = self._resource_watchdog.limit_for(tier_name)
        if limit and limit.max_items:
            return limit.max_items

        config = getattr(tier, "config", None)
        if isinstance(config, dict):
            candidate = config.get("max_capacity")
            try:
                if candidate is not None:
                    capacity = int(candidate)
                    if capacity > 0:
                        return capacity
            except (TypeError, ValueError):
                logger.debug(
                    "Ignoring invalid max_capacity %r for %s tier", candidate, tier_name
                )

        candidate = getattr(tier, "capacity", None)
        try:
            if candidate is not None:
                capacity = int(candidate)
                if capacity > 0:
                    return capacity
        except (TypeError, ValueError):
            logger.debug(
                "Ignoring invalid capacity %r for %s tier", candidate, tier_name
            )
        return None

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
            except Exception:  # noqa: BLE001 - defensive conversion
                metadata = {}
            return metadata if isinstance(metadata, dict) else {}

        if isinstance(memory, Mapping):
            metadata = memory.get("metadata")
            if isinstance(metadata, MemoryMetadata):
                try:
                    metadata = metadata.model_dump()
                except Exception:  # noqa: BLE001 - defensive conversion
                    metadata = {}
            return metadata if isinstance(metadata, dict) else {}

        return {}

    def _partition_metadata_fields(
        self, metadata: Mapping[str, Any]
    ) -> tuple[dict[str, Any], dict[str, Any]]:
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

    async def _refresh_capacity_pressure(self) -> None:
        """Collect utilisation snapshots and update the pressure adapter."""

        adapter = self._capacity_adapter
        if adapter is None:
            return

        for tier_name in (self.STM_TIER, self.MTM_TIER, self.LTM_TIER):
            tier = getattr(self, f"_{tier_name}", None)
            if tier is None:
                continue

            counter = getattr(tier, "count", None)
            if counter is None:
                continue

            if not callable(counter):
                logger.debug(
                    "Skipping non-callable count handler for %s tier", tier_name
                )
                continue

            capacity = self._resolve_tier_capacity(tier_name, tier)
            if not capacity:
                adapter.observe(tier_name, 0.0)
                continue

            try:
                current = counter({})
                if asyncio.iscoroutine(current):
                    current = await current
                current_value = float(current)
            except Exception:  # noqa: BLE001 - best effort metric
                logger.debug(
                    "Unable to collect utilisation for %s tier", tier_name, exc_info=True
                )
                continue

            try:
                ratio = max(0.0, min(1.0, current_value / float(capacity)))
            except ZeroDivisionError:
                ratio = 1.0

            adapter.observe(tier_name, ratio)

        if getattr(self, "_metrics", None) and self._metrics.enabled:
            self._metrics.update_capacity_snapshot(adapter.snapshot())
    
    def _get_tier_by_name(self, tier_name: str):
        """
        Get a tier instance by name.
        
        Args:
            tier_name: Tier name ("stm", "mtm", "ltm")
            
        Returns:
            Tier instance
            
        Raises:
            InvalidTierError: If tier name is invalid
        """
        if tier_name == self.STM_TIER:
            return self._stm
        elif tier_name == self.MTM_TIER:
            return self._mtm
        elif tier_name == self.LTM_TIER:
            return self._ltm
        else:
            raise InvalidTierError(f"Invalid tier name: {tier_name}")
    
    #-----------------------------------------------------------------------
    # Core Memory Operations
    #-----------------------------------------------------------------------
    
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
        """
        Add a new memory to the system.
        
        By default, memories start in STM and may be consolidated to MTM/LTM
        based on importance and access patterns.
        
        Args:
            content: Memory content (can be text, dict, or structured data)
            summary: Optional summary of the content
            importance: Importance score (0.0 to 1.0)
            metadata: Additional metadata
            tags: Tags for categorization
            embedding: Optional pre-computed embedding vector
            initial_tier: Initial storage tier (default is STM)
            
        Returns:
            Memory ID
            
        Raises:
            MemoryCapacityError: If the target tier is at capacity and cannot accept more items
            MemoryManagerOperationError: If the add operation fails
        """
        self._ensure_initialized()
        
        # Determine initial tier
        initial_tier = initial_tier or self.STM_TIER
        
        # Get tier instance
        tier = self._get_tier_by_name(initial_tier)
        
        # Sanitize core payload
        sanitized_summary = self._sanitizer.sanitize_optional_text(
            "summary", summary
        )

        if isinstance(content, str):
            sanitized_text = self._sanitizer.sanitize_text("content", content)
            sanitized_json: dict[str, Any] | None = None
            sanitized_raw: Any | None = None
        else:
            sanitized_payload = self._sanitizer.sanitize_value("content", content)
            sanitized_text = None
            sanitized_json = sanitized_payload if isinstance(sanitized_payload, dict) else None
            sanitized_raw = None if sanitized_json is not None else sanitized_payload

        memory_content = MemoryContent(
            text=sanitized_text,
            summary=sanitized_summary,
            json_data=sanitized_json if sanitized_text is None else None,
            raw_content=sanitized_raw if sanitized_text is None else None,
        )

        metadata_dict = metadata or {}
        if not isinstance(metadata_dict, dict):
            metadata_dict = {"data": metadata_dict}

        sanitized_metadata, metadata_tags = self._sanitizer.sanitize_metadata(
            metadata_dict
        )
        core_metadata, extra_metadata = self._partition_metadata_fields(
            sanitized_metadata
        )
        sanitized_tag_map = self._sanitizer.merge_tag_maps(
            metadata_tags,
            self._sanitizer.sanitize_tag_list(tags or []),
        )

        memory_metadata = MemoryMetadata(
            importance=importance,
            tags=sanitized_tag_map,
            **core_metadata,
        )

        if extra_metadata:
            extra_dict = dict(extra_metadata)
            nested_additional = extra_dict.pop("additional_metadata", None)

            if isinstance(nested_additional, Mapping):
                try:
                    memory_metadata.additional_metadata.update(nested_additional)
                except Exception:  # noqa: BLE001 - defensive fallback
                    for key, value in nested_additional.items():
                        memory_metadata.additional_metadata[key] = value
            elif nested_additional is not None:
                memory_metadata.additional_metadata["additional_metadata"] = (
                    nested_additional
                )

            for key, value in extra_dict.items():
                memory_metadata.additional_metadata[key] = value
        
        # Create memory item
        memory_item = MemoryItem(
            content=memory_content,
            metadata=memory_metadata,
        )
        
        serialized_memory = memory_item.model_dump()

        memory_id: str | None = None
        try:
            async with self._backpressure.slot(initial_tier):
                await self._resource_watchdog.ensure_capacity(initial_tier, tier)

                # Store in tier with watchdog-enforced timeout limits
                memory_id = await self._resource_watchdog.store(
                    initial_tier,
                    tier,
                    serialized_memory,
                )

            # Update working memory with new memory if it's relevant to current context
            # This would require calculating relevance, which we're keeping simple for now
            if self._current_context and memory_id is not None:
                # For demonstration, we'll add any memory with importance > 0.7 to working memory
                if importance > 0.7:
                    memory_data = await tier.retrieve(memory_id)
                    if memory_data:
                        # Convert to MemoryItem if needed
                        memory_item = (
                            memory_data
                            if isinstance(memory_data, MemoryItem)
                            else MemoryItem.model_validate(memory_data)
                        )

                        self._working_memory.add_item(
                            WorkingMemoryItem(
                                memory=memory_item,
                                source_tier=initial_tier,
                                relevance=0.9,  # High relevance for highly important memories
                            )
                        )

            if memory_id is None:
                raise MemoryManagerOperationError(
                    f"Failed to store memory in {initial_tier} tier"
                )

            logger.debug(f"Added memory {memory_id} to {initial_tier} tier")

            await self._audit_trail.record_creation(
                {**serialized_memory, "id": str(memory_id)},
                tier=initial_tier,
            )
            return memory_id
        except MemoryBackpressureError as exc:
            logger.warning(
                "Back-pressure rejected memory write to %s tier: %s",
                initial_tier,
                exc,
            )
            raise
        except MemoryCapacityError as exc:
            logger.warning(
                "Rejected memory write to %s tier due to capacity limits: %s",
                initial_tier,
                exc,
            )
            raise
        except asyncio.TimeoutError as exc:
            logger.exception(
                "Timed out storing memory in %s tier after watchdog enforcement",
                initial_tier,
            )
            raise MemoryManagerOperationError(
                f"Timed out storing memory in {initial_tier} tier"
            ) from exc
        except Exception as e:
            logger.exception(f"Failed to add memory to {initial_tier} tier")
            raise MemoryManagerOperationError(
                f"Failed to add memory: {str(e)}"
            ) from e
    
    async def retrieve_memory(
        self,
        memory_id: str,
        tier: Optional[str] = None,
        scope: MemoryRetrievalScope | None = None,
    ) -> Optional[MemoryItem]:
        """
        Retrieve a specific memory by ID.
        
        Args:
            memory_id: Memory ID
            tier: Optional tier to search in (searches all tiers if not specified)
            
        Returns:
            MemoryItem if found, otherwise None
            
        Raises:
            MemoryManagerOperationError: If the retrieve operation fails
        """
        self._ensure_initialized()

        scope_obj = self._normalize_scope(scope)

        try:
            # If tier is specified, search only that tier
            if tier:
                tier_instance = self._get_tier_by_name(tier)
                memory_data = await tier_instance.retrieve(memory_id)
                if not memory_data:
                    return None

                metadata = self._extract_metadata_dict(memory_data)
                self._assert_memory_access(memory_id, metadata, scope_obj, "retrieve")
                await tier_instance.access(memory_id)
                return memory_data

            # Otherwise, search all tiers starting from STM (most recent)
            for tier_name in [self.STM_TIER, self.MTM_TIER, self.LTM_TIER]:
                tier_instance = self._get_tier_by_name(tier_name)
                memory_data = await tier_instance.retrieve(memory_id)
                if memory_data:
                    metadata = self._extract_metadata_dict(memory_data)
                    self._assert_memory_access(
                        memory_id, metadata, scope_obj, "retrieve"
                    )
                    await tier_instance.access(memory_id)
                    return memory_data

            # Memory not found in any tier
            return None
        except MemoryAccessDeniedError:
            raise
        except InvalidTierError as e:
            # Re-raise with more specific error
            raise e
        except Exception as e:
            logger.exception(f"Failed to retrieve memory {memory_id}")
            raise MemoryManagerOperationError(
                f"Failed to retrieve memory: {str(e)}"
            ) from e
    
    async def update_memory(
        self,
        memory_id: str,
        content: Optional[Any] = None,
        summary: Optional[str] = None,
        importance: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
    ) -> bool:
        """
        Update an existing memory.
        
        Args:
            memory_id: Memory ID
            content: New content (if None, keeps existing content)
            summary: New summary (if None, keeps existing summary)
            importance: New importance (if None, keeps existing importance)
            metadata: New metadata (if None, keeps existing metadata)
            tags: New tags (if None, keeps existing tags)
            
        Returns:
            bool: True if the update was successful
            
        Raises:
            MemoryNotFoundError: If memory with the given ID is not found
            MemoryManagerOperationError: If the update operation fails
        """
        self._ensure_initialized()
        
        # First, find the memory in all tiers
        memory_tier = None
        memory_data = None
        
        for tier_name in [self.STM_TIER, self.MTM_TIER, self.LTM_TIER]:
            tier_instance = self._get_tier_by_name(tier_name)
            data = await tier_instance.retrieve(memory_id)
            if data:
                memory_tier = tier_name
                memory_data = data
                break
        
        if not memory_data or not memory_tier:
            raise MemoryNotFoundError(f"Memory {memory_id} not found in any tier")
        
        try:
            content_updates: dict[str, Any] = {}
            if content is not None:
                if isinstance(content, str):
                    sanitized_text = self._sanitizer.sanitize_text("content", content)
                    content_updates["text"] = sanitized_text
                else:
                    sanitized_payload = self._sanitizer.sanitize_value("content", content)
                    if isinstance(sanitized_payload, dict):
                        content_updates["json_data"] = sanitized_payload
                    elif sanitized_payload is not None:
                        content_updates["text"] = str(sanitized_payload)

            if summary is not None:
                sanitized_summary = self._sanitizer.sanitize_text("summary", summary)
                content_updates["summary"] = sanitized_summary

            metadata_updates: dict[str, Any] = {}
            if importance is not None:
                metadata_updates["importance"] = importance

            metadata_payload: dict[str, Any] | None = None
            if metadata is not None:
                metadata_payload = metadata if isinstance(metadata, dict) else {"data": metadata}

            sanitized_metadata: dict[str, Any] = {}
            metadata_tag_map: dict[str, Any] = {}
            if metadata_payload is not None:
                sanitized_metadata, metadata_tag_map = self._sanitizer.sanitize_metadata(
                    metadata_payload
                )
                for key, value in sanitized_metadata.items():
                    metadata_updates[key] = value

            metadata_source: dict[str, Any] = {}
            if isinstance(memory_data, dict):
                raw_metadata = memory_data.get("metadata")
                if isinstance(raw_metadata, dict):
                    metadata_source = dict(raw_metadata)
            else:
                existing_metadata = getattr(memory_data, "metadata", None)
                if existing_metadata is not None:
                    if hasattr(existing_metadata, "model_dump"):
                        try:
                            dumped = existing_metadata.model_dump()  # type: ignore[call-arg]
                        except Exception:  # noqa: BLE001
                            dumped = {}
                        metadata_source = dumped if isinstance(dumped, dict) else {}
                    elif hasattr(existing_metadata, "dict"):
                        try:
                            dumped = existing_metadata.dict()  # type: ignore[call-arg]
                        except Exception:  # noqa: BLE001
                            dumped = {}
                        metadata_source = dumped if isinstance(dumped, dict) else {}

            raw_existing_tags = metadata_source.get("tags", {}) if metadata_source else {}
            existing_tags = self._sanitizer.sanitize_tag_map(raw_existing_tags)

            explicit_tags = self._sanitizer.sanitize_tag_list(tags) if tags is not None else {}

            combined_tags = self._sanitizer.merge_tag_maps(
                existing_tags,
                metadata_tag_map,
                explicit_tags,
            )

            if tags is not None or metadata_tag_map or combined_tags != existing_tags:
                metadata_updates["tags"] = combined_tags

            tier_instance = self._get_tier_by_name(memory_tier)

            success = await tier_instance.update(
                memory_id,
                content=content_updates if content_updates else None,
                metadata=metadata_updates if metadata_updates else None,
            )
            
            # Note: Working memory update would be handled here if needed
            # Currently WorkingMemoryBuffer doesn't have update_item method
            
            return success
        except MemoryValidationError:
            raise
        except Exception as e:
            logger.exception(f"Failed to update memory {memory_id}")
            raise MemoryManagerOperationError(
                f"Failed to update memory: {str(e)}"
            ) from e
    
    async def delete_memory(
        self,
        memory_id: str,
        tier: Optional[str] = None,
    ) -> bool:
        """
        Delete a memory by ID.
        
        Args:
            memory_id: Memory ID
            tier: Optional tier to delete from (tries all tiers if not specified)
            
        Returns:
            bool: True if the deletion was successful
            
        Raises:
            MemoryManagerOperationError: If the delete operation fails
        """
        self._ensure_initialized()
        
        try:
            success = False
            
            # If tier is specified, delete only from that tier
            if tier:
                tier_instance = self._get_tier_by_name(tier)
                success = await tier_instance.delete(memory_id)
            else:
                # Otherwise, try to delete from all tiers
                for tier_name in [self.STM_TIER, self.MTM_TIER, self.LTM_TIER]:
                    tier_instance = self._get_tier_by_name(tier_name)
                    if await tier_instance.delete(memory_id):
                        success = True
            
            # Remove from working memory if deleted
            if success:
                self._working_memory.remove_item(memory_id)
            
            return success
        except InvalidTierError as e:
            # Re-raise with more specific error
            raise e
        except Exception as e:
            logger.exception(f"Failed to delete memory {memory_id}")
            raise MemoryManagerOperationError(
                f"Failed to delete memory: {str(e)}"
            ) from e

    async def transfer_memory(
        self,
        memory_id: str,
        target_tier: Union[str, MemoryTier],
    ) -> MemoryItem:
        """Move a memory from its current tier into ``target_tier``."""

        self._ensure_initialized()

        try:
            resolved_target = (
                target_tier.storage_key
                if isinstance(target_tier, MemoryTier)
                else MemoryTier.from_string(str(target_tier)).storage_key
            )
        except ValueError as exc:  # pragma: no cover - defensive guard
            raise InvalidTierError(f"Unknown target tier: {target_tier!r}") from exc

        source_tier_name: Optional[str] = None
        memory_item: Optional[MemoryItem] = None

        for tier_name in [self.STM_TIER, self.MTM_TIER, self.LTM_TIER]:
            tier_instance = self._get_tier_by_name(tier_name)
            fetched = await tier_instance.retrieve(memory_id)
            if fetched:
                source_tier_name = tier_name
                memory_item = (
                    fetched
                    if isinstance(fetched, MemoryItem)
                    else MemoryItem.model_validate(fetched)
                )
                break

        if memory_item is None or source_tier_name is None:
            raise MemoryNotFoundError(f"Memory {memory_id} not found in any tier")

        if source_tier_name == resolved_target:
            return memory_item

        source_tier = self._get_tier_by_name(source_tier_name)
        target_tier_instance = self._get_tier_by_name(resolved_target)

        if getattr(memory_item, "metadata", None):
            memory_item.metadata.tier = resolved_target
            if hasattr(memory_item.metadata, "updated_at"):
                memory_item.metadata.updated_at = datetime.now(timezone.utc)

        payload = memory_item.model_dump()

        try:
            await target_tier_instance.store(payload, memory_id=memory_id)
        except Exception as exc:  # noqa: BLE001
            logger.exception(
                "Failed to transfer memory %s to %s", memory_id, resolved_target
            )
            raise MemoryManagerOperationError(
                f"Failed to move memory to {resolved_target}: {exc}"
            ) from exc

        try:
            await source_tier.delete(memory_id)
        except Exception:  # noqa: BLE001 - log and continue, target copy already exists
            logger.warning(
                "Failed to delete memory %s from %s after transfer",
                memory_id,
                source_tier_name,
                exc_info=True,
            )

        if self._working_memory and self._working_memory.contains(memory_id):
            self._working_memory.remove_item(memory_id)

        moved = await target_tier_instance.retrieve(memory_id)
        return (
            moved
            if isinstance(moved, MemoryItem)
            else MemoryItem.model_validate(moved)
        )

    #-----------------------------------------------------------------------
    # Search and Retrieval
    #-----------------------------------------------------------------------
    
    async def search_memories(
        self,
        query: Optional[str] = None,
        embedding: Optional[List[float]] = None,
        tags: Optional[List[str]] = None,
        metadata_filters: Optional[Dict[str, Any]] = None,
        limit: int = 10,
        min_relevance: float = 0.0,
        tiers: Optional[List[str]] = None,
        scope: MemoryRetrievalScope | None = None,
    ) -> List[Dict[str, Any]]:
        """
        Search for memories across all tiers.
        
        Args:
            query: Text query
            embedding: Optional query embedding for vector search
            tags: Optional tags to filter by
            metadata_filters: Optional metadata field filters
            limit: Maximum number of results
            min_relevance: Minimum relevance score (0.0 to 1.0)
            tiers: Optional list of tiers to search in
            
        Returns:
            List of relevant memories
            
        Raises:
            MemoryManagerOperationError: If the search operation fails
        """
        self._ensure_initialized()

        scope_obj = self._normalize_scope(scope)
        
        try:
            # Determine which tiers to search
            search_tiers = tiers or [self.STM_TIER, self.MTM_TIER, self.LTM_TIER]
            all_results = []
            
            # Build filter dictionary from tags
            if tags:
                if not metadata_filters:
                    metadata_filters = {}
                for tag in tags:
                    metadata_filters[f"metadata.tags.{tag}"] = True
            
            # Search each tier
            for tier_name in search_tiers:
                try:
                    tier_instance = self._get_tier_by_name(tier_name)
                    
                    # Create search options
                    tier_search_results = await tier_instance.search(
                        query=query,
                        embedding=embedding,
                        filters=metadata_filters,
                        limit=limit,
                    )
                    
                    # Extract results from MemorySearchResults and convert to dicts
                    for search_result in tier_search_results.results:
                        if not self._is_memory_visible(
                            search_result.memory, scope_obj
                        ):
                            continue

                        result_dict = search_result.memory.model_dump()
                        result_dict["tier"] = tier_name
                        # Add relevance score from search result
                        result_dict["_relevance"] = search_result.relevance
                        all_results.append(result_dict)
                    
                except Exception as e:
                    logger.error(f"Error searching tier {tier_name}: {str(e)}")
            
            # Sort results by relevance (if available) or importance
            def get_sort_key(item):
                relevance = item.get("_relevance", 0.0)
                importance = item.get("metadata", {}).get("importance", 0.0)
                # Weigh relevance higher than importance
                return (relevance * 0.7) + (importance * 0.3)
            
            sorted_results = sorted(
                all_results,
                key=get_sort_key,
                reverse=True,
            )
            
            # Limit final results
            return sorted_results[:limit]
        except Exception as e:
            logger.exception("Failed to search memories")
            raise MemoryManagerOperationError(
                f"Failed to search memories: {str(e)}"
            ) from e
    
    #-----------------------------------------------------------------------
    # Context Management
    #-----------------------------------------------------------------------
    
    async def update_context(
        self,
        context_data: Dict[str, Any],
        embedding: Optional[List[float]] = None,
    ) -> None:
        """
        Update the current context to trigger relevant memory retrieval.
        
        This method updates the system's understanding of the current context,
        such as the current conversation, user input, goals, etc. It triggers
        background retrieval of relevant memories for the working memory buffer.
        
        Args:
            context_data: Dictionary with current context information
            embedding: Optional pre-computed embedding of the context
            
        Raises:
            MemoryManagerOperationError: If the context update fails
        """
        self._ensure_initialized()
        
        try:
            # Update current context
            self._current_context = context_data
            self._current_context_embedding = embedding
            
            # Extract text for text search if no embedding provided
            query_text = None
            if not embedding:
                # Try to extract text from context_data
                if "text" in context_data:
                    query_text = context_data["text"]
                elif "query" in context_data:
                    query_text = context_data["query"]
                elif "input" in context_data:
                    query_text = context_data["input"]
                elif "message" in context_data:
                    query_text = context_data["message"]
            
            # Clear working memory
            self._working_memory.clear()
            
            # Search for relevant memories in all tiers
            relevant_memories = await self.search_memories(
                query=query_text,
                embedding=embedding,
                limit=20,  # Get more than needed for diversity
                min_relevance=0.3,  # Lower threshold to get more diverse results
            )
            
            # Add relevant memories to working memory
            for memory in relevant_memories:
                memory_id = memory.get("id")
                tier = memory.get("tier")
                relevance = memory.get("_relevance", 0.5)
                
                if memory_id and tier:
                    # Convert dict to MemoryItem if needed
                    memory_item = memory.get('memory') if isinstance(memory.get('memory'), MemoryItem) else MemoryItem.model_validate(memory)
                    
                    self._working_memory.add_item(
                        WorkingMemoryItem(
                            memory=memory_item,
                            source_tier=tier,
                            relevance=relevance,
                        )
                    )
            
            logger.debug(f"Updated context and working memory with {len(relevant_memories)} relevant memories")
        except Exception as e:
            logger.exception("Failed to update context")
            raise MemoryManagerOperationError(
                f"Failed to update context: {str(e)}"
            ) from e
    
    async def get_prompt_context_memories(
        self,
        max_memories: int = 5,
        max_tokens_per_memory: int = 150,
    ) -> List[Dict[str, Any]]:
        """
        Get the most relevant memories for injection into the agent's prompt.
        
        This method is used by the prompt builder to inject relevant context
        from the memory system into the agent's prompt.
        
        Args:
            max_memories: Maximum number of memories to include
            max_tokens_per_memory: Maximum tokens per memory
            
        Returns:
            List of formatted memory dictionaries
            
        Raises:
            MemoryManagerOperationError: If the prompt context retrieval fails
        """
        self._ensure_initialized()
        
        try:
            # Get the most relevant items from working memory
            working_memory_items = self._working_memory.get_most_relevant_items(max_memories)
            
            # Format memories for prompt inclusion
            formatted_memories = []
            
            for item in working_memory_items:
                memory_data = item.memory.model_dump()
                
                # Format the memory for prompt inclusion
                formatted_memory = {
                    "id": memory_data.get("id"),
                    "content": memory_data.get("content", {}).get("text") or "[Structured Data]",
                    "summary": memory_data.get("content", {}).get("summary") or None,
                    "importance": memory_data.get("metadata", {}).get("importance", 0.5),
                    "created_at": memory_data.get("metadata", {}).get("created_at"),
                    "relevance": item.relevance,
                    "tier": item.source_tier,
                }
                
                # Truncate content to max_tokens_per_memory
                # This is a simple approximation, a real implementation would use a proper tokenizer
                text = formatted_memory["content"]
                if text and isinstance(text, str):
                    words = text.split()
                    if len(words) > max_tokens_per_memory / 0.75:  # Approximate tokens by words
                        formatted_memory["content"] = " ".join(words[:int(max_tokens_per_memory / 0.75)]) + "..."
                
                formatted_memories.append(formatted_memory)
            
            return formatted_memories
        except Exception as e:
            logger.exception("Failed to get prompt context memories")
            raise MemoryManagerOperationError(
                f"Failed to get prompt context memories: {str(e)}"
            ) from e
    
    async def clear_context(self) -> None:
        """
        Clear the current context and working memory buffer.
        
        This method is typically called at the end of a conversation or
        when switching to a completely different task.
        
        Raises:
            MemoryManagerOperationError: If the clear context operation fails
        """
        self._ensure_initialized()
        
        try:
            # Clear current context
            self._current_context = {}
            self._current_context_embedding = None
            
            # Clear working memory
            self._working_memory.clear()
            
            logger.debug("Cleared context and working memory")
        except Exception as e:
            logger.exception("Failed to clear context")
            raise MemoryManagerOperationError(
                f"Failed to clear context: {str(e)}"
            ) from e
    
    #-----------------------------------------------------------------------
    # Memory Lifecycle Management
    #-----------------------------------------------------------------------
    
    async def consolidate_memory(
        self,
        memory_id: str,
        source_tier: str,
        target_tier: str,
        additional_metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """
        Explicitly consolidate a memory from one tier to another.
        
        This method allows for manual consolidation of a memory, 
        in addition to the automatic consolidation done by the system.
        
        Args:
            memory_id: Memory ID
            source_tier: Source tier ("stm", "mtm", "ltm")
            target_tier: Target tier ("stm", "mtm", "ltm")
            additional_metadata: Optional additional metadata to add during consolidation
            
        Returns:
            The ID of the consolidated memory in the target tier (may be the same or different)
            
        Raises:
            MemoryNotFoundError: If memory with the given ID is not found
            InvalidTierError: If source or target tier is invalid
            MemoryManagerOperationError: If the consolidation fails
        """
        self._ensure_initialized()
        
        # Validate tiers
        if source_tier not in [self.STM_TIER, self.MTM_TIER, self.LTM_TIER]:
            raise InvalidTierError(f"Invalid source tier: {source_tier}")
        
        if target_tier not in [self.STM_TIER, self.MTM_TIER, self.LTM_TIER]:
            raise InvalidTierError(f"Invalid target tier: {target_tier}")
        
        # Get source and target tier instances
        source_tier_instance = self._get_tier_by_name(source_tier)
        target_tier_instance = self._get_tier_by_name(target_tier)
        
        pipeline_key = f"{source_tier}:{memory_id}->{target_tier}"

        metrics = getattr(self, "_metrics", None)
        event_publisher = getattr(self, "_event_publisher", None)

        try:
            while True:
                decision = await self._consolidation_guard.reserve(pipeline_key)
                if not decision.proceed:
                    if decision.result is None:
                        continue
                    if event_publisher is not None:
                        await event_publisher.consolidation_completed(
                            memory_id=memory_id,
                            source_tier=source_tier,
                            target_tier=target_tier,
                            status="cached",
                            duration_seconds=None,
                            result_id=str(decision.result),
                        )
                    return decision.result

                reservation = decision.reservation
                if reservation is None:
                    if decision.result is not None and event_publisher is not None:
                        await event_publisher.consolidation_completed(
                            memory_id=memory_id,
                            source_tier=source_tier,
                            target_tier=target_tier,
                            status="cached",
                            duration_seconds=None,
                            result_id=str(decision.result),
                        )
                    return decision.result

                async with reservation:
                    started = perf_counter()
                    memory_data = await source_tier_instance.retrieve(memory_id)
                    if not memory_data:
                        raise MemoryNotFoundError(
                            f"Memory {memory_id} not found in {source_tier} tier"
                        )

                    if additional_metadata:
                        if isinstance(memory_data, MemoryItem):
                            metadata = memory_data.metadata
                            tags = metadata.tags
                            for key, value in additional_metadata.items():
                                if key == "tags" and isinstance(value, dict):
                                    tags.update(value)
                                else:
                                    tags[f"_meta_{key}"] = value
                            metadata.tags = tags
                        else:
                            metadata = memory_data.get("metadata", {})
                            for key, value in additional_metadata.items():
                                if key == "tags":
                                    tags = metadata.get("tags", {})
                                    tags.update(value)
                                    metadata["tags"] = tags
                                else:
                                    metadata[key] = value

                            memory_data["metadata"] = metadata

                    async def runner(transaction: ConsolidationTransaction) -> Any:
                        stored_id = await transaction.stage(
                            lambda: target_tier_instance.store(memory_data),
                            rollback=lambda new_id: self._delete_if_supported(
                                target_tier_instance,
                                new_id,
                                context=f"consolidation {pipeline_key}",
                            ),
                            description="store_target",
                        )

                        if not stored_id:
                            raise ConsolidationSkip(
                                f"Target tier {target_tier} did not return an identifier"
                            )

                        if source_tier != target_tier:
                            await transaction.stage(
                                lambda: source_tier_instance.delete(memory_id),
                                description="delete_source",
                            )

                        return stored_id

                    try:
                        new_id = await self._consolidation_pipeline.run(
                            pipeline_key, runner
                        )
                        duration = perf_counter() - started
                    except ConsolidationSkip as exc:
                        duration = perf_counter() - started
                        if metrics is not None:
                            metrics.record_consolidation(
                                source=source_tier,
                                target=target_tier,
                                duration_seconds=duration,
                                succeeded=False,
                            )
                        if event_publisher is not None:
                            await event_publisher.consolidation_completed(
                                memory_id=memory_id,
                                source_tier=source_tier,
                                target_tier=target_tier,
                                status="skipped",
                                duration_seconds=duration,
                                result_id=None,
                                error=str(exc),
                            )
                        raise MemoryManagerOperationError(
                            f"Failed to consolidate memory {memory_id}: {exc}"
                        ) from exc
                    except Exception as exc:
                        duration = perf_counter() - started
                        if metrics is not None:
                            metrics.record_consolidation(
                                source=source_tier,
                                target=target_tier,
                                duration_seconds=duration,
                                succeeded=False,
                            )
                        if event_publisher is not None:
                            await event_publisher.consolidation_completed(
                                memory_id=memory_id,
                                source_tier=source_tier,
                                target_tier=target_tier,
                                status="error",
                                duration_seconds=duration,
                                result_id=None,
                                error=str(exc),
                            )
                        logger.exception("Failed to consolidate memory %s", memory_id)
                        raise MemoryManagerOperationError(
                            f"Failed to consolidate memory: {str(exc)}"
                        ) from exc

                    reservation.commit(new_id)
                    if metrics is not None:
                        metrics.record_consolidation(
                            source=source_tier,
                            target=target_tier,
                            duration_seconds=duration,
                            succeeded=True,
                        )
                    if event_publisher is not None:
                        await event_publisher.consolidation_completed(
                            memory_id=memory_id,
                            source_tier=source_tier,
                            target_tier=target_tier,
                            status="success",
                            duration_seconds=duration,
                            result_id=str(new_id) if new_id is not None else None,
                        )
                    await self._audit_trail.record_consolidation(
                        memory_data,
                        source_tier=source_tier,
                        target_tier=target_tier,
                        new_memory_id=str(new_id) if new_id is not None else None,
                    )
                    return new_id
        except Exception as e:
            if isinstance(e, (MemoryNotFoundError, InvalidTierError)):
                raise
            
            logger.exception(f"Failed to consolidate memory {memory_id}")
            raise MemoryManagerOperationError(
                f"Failed to consolidate memory: {str(e)}"
            ) from e
    
    async def strengthen_memory(
        self,
        memory_id: str,
        tier: Optional[str] = None,
        strengthen_amount: float = 0.1,
    ) -> bool:
        """
        Strengthen a memory to make it less likely to be forgotten.
        
        Args:
            memory_id: Memory ID
            tier: Optional tier to strengthen in (tries all tiers if not specified)
            strengthen_amount: Amount to strengthen by (0.0 to 1.0)
            
        Returns:
            bool: True if the strengthening was successful
            
        Raises:
            MemoryNotFoundError: If memory with the given ID is not found
            MemoryManagerOperationError: If the strengthen operation fails
        """
        self._ensure_initialized()
        
        try:
            success = False
            
            # If tier is specified, strengthen only in that tier
            if tier:
                tier_instance = self._get_tier_by_name(tier)
                return await tier_instance.strengthen(memory_id, strengthen_amount)
            
            # Otherwise, try to strengthen in all tiers
            for tier_name in [self.STM_TIER, self.MTM_TIER, self.LTM_TIER]:
                tier_instance = self._get_tier_by_name(tier_name)
                if await tier_instance.exists(memory_id):
                    if await tier_instance.strengthen(memory_id, strengthen_amount):
                        success = True
                    break  # Stop after strengthening in first tier where memory exists
            
            return success
        except Exception as e:
            if isinstance(e, InvalidTierError):
                raise
            
            logger.exception(f"Failed to strengthen memory {memory_id}")
            if isinstance(e, MemoryNotFoundError):
                raise
            
            raise MemoryManagerOperationError(
                f"Failed to strengthen memory: {str(e)}"
            ) from e
    
    async def decay_memory(
        self,
        memory_id: str,
        tier: Optional[str] = None,
        decay_amount: float = 0.1,
    ) -> bool:
        """
        Explicitly decay a memory to make it more likely to be forgotten.
        
        Args:
            memory_id: Memory ID
            tier: Optional tier to decay in (tries all tiers if not specified)
            decay_amount: Amount to decay by (0.0 to 1.0)
            
        Returns:
            bool: True if the decay was successful
            
        Raises:
            MemoryNotFoundError: If memory with the given ID is not found
            MemoryManagerOperationError: If the decay operation fails
        """
        self._ensure_initialized()
        
        try:
            success = False
            
            # If tier is specified, decay only in that tier
            if tier:
                tier_instance = self._get_tier_by_name(tier)
                return await tier_instance.decay(memory_id, decay_amount)
            
            # Otherwise, try to decay in all tiers
            for tier_name in [self.STM_TIER, self.MTM_TIER, self.LTM_TIER]:
                tier_instance = self._get_tier_by_name(tier_name)
                if await tier_instance.exists(memory_id):
                    if await tier_instance.decay(memory_id, decay_amount):
                        success = True
                    break  # Stop after decaying in first tier where memory exists
            
            return success
        except Exception as e:
            if isinstance(e, InvalidTierError):
                raise
            
            logger.exception(f"Failed to decay memory {memory_id}")
            if isinstance(e, MemoryNotFoundError):
                raise
            
            raise MemoryManagerOperationError(
                f"Failed to decay memory: {str(e)}"
            ) from e
    
    #-----------------------------------------------------------------------
    # System Management
    #-----------------------------------------------------------------------
    
    async def get_system_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the memory system.
        
        Returns:
            Dictionary of statistics
            
        Raises:
            MemoryManagerOperationError: If the stats retrieval fails
        """
        self._ensure_initialized()
        
        try:
            stats = {
                "timestamp": time.time(),
                "tiers": {},
                "working_memory": {
                    "size": len(self._working_memory),
                    "capacity": self._working_memory.capacity,
                }
            }
            
            # Get stats for each tier
            for tier_name, tier_instance in [
                (self.STM_TIER, self._stm),
                (self.MTM_TIER, self._mtm),
                (self.LTM_TIER, self._ltm),
            ]:
                tier_stats = await tier_instance.get_stats()
                stats["tiers"][tier_name] = tier_stats
            
            # Calculate overall stats
            total_memories = sum(
                tier_stats.get("total_memories", 0)
                for tier_stats in stats["tiers"].values()
            )
            
            stats["total_memories"] = total_memories
            
            return stats
        except Exception as e:
            logger.exception("Failed to get system stats")
            raise MemoryManagerOperationError(
                f"Failed to get system stats: {str(e)}"
            ) from e
    
    async def run_maintenance(self) -> Dict[str, Any]:
        """
        Run maintenance tasks on the memory system.

        This includes tasks like:
        - Consolidating memories between tiers
        - Decaying memories
        - Cleaning up expired memories
        - Optimizing storage

        Returns:
            Dictionary of maintenance results

        Raises:
            MemoryManagerOperationError: If the maintenance fails
        """
        self._ensure_initialized()

        orchestrator = self._ensure_maintenance_orchestrator()

        result = await orchestrator.run_cycle(triggered_by="manual")
        if result.get("status") == "error":
            errors = result.get("errors", [])
            message = "Maintenance cycle reported errors"
            if errors:
                message = f"Maintenance cycle reported errors: {', '.join(errors)}"
            raise MemoryManagerOperationError(message)

        try:
            await self._refresh_capacity_pressure()
        except Exception as exc:  # noqa: BLE001 - surface as debug noise only
            logger.debug("Capacity pressure refresh failed after manual maintenance", exc_info=True)

        return result
