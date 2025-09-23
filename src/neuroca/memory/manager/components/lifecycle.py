"""Lifecycle management helpers for the asynchronous memory manager."""

from __future__ import annotations

import asyncio
import contextlib

from neuroca.memory.exceptions import (
    InvalidTierError,
    MemoryManagerInitializationError,
    MemoryManagerOperationError,
)
from neuroca.memory.manager.maintenance import MaintenanceOrchestrator
from neuroca.memory.tiers.ltm.core import LongTermMemoryTier
from neuroca.memory.tiers.mtm.core import MediumTermMemoryTier
from neuroca.memory.tiers.stm.core import ShortTermMemoryTier

from .base import LOGGER


class MemoryManagerLifecycleMixin:
    """Initialisation, shutdown, and tier access helpers."""

    async def initialize(self) -> None:
        """Initialise storage tiers and supporting services."""

        if self._initialized:
            LOGGER.warning("Memory Manager already initialized")
            return

        try:
            LOGGER.info("Initializing Memory Manager")

            self._shutdown_event.clear()

            if self._stm_instance:
                self._stm = self._stm_instance
                if hasattr(self._stm, "initialize"):
                    await self._stm.initialize()
            else:
                self._stm = ShortTermMemoryTier(
                    backend_type=self._stm_storage_type,
                    backend_config=self._backend_config,
                    config=self._stm_config,
                )
                await self._stm.initialize()

            if self._mtm_instance:
                self._mtm = self._mtm_instance
                if hasattr(self._mtm, "initialize"):
                    await self._mtm.initialize()
            else:
                self._mtm = MediumTermMemoryTier(
                    backend_type=self._mtm_storage_type,
                    backend_config=self._backend_config,
                    config=self._mtm_config,
                )
                await self._mtm.initialize()

            if self._ltm_instance:
                self._ltm = self._ltm_instance
                if hasattr(self._ltm, "initialize"):
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

            if self._maintenance_interval > 0:
                self._start_maintenance_task()

            self._initialized = True
            LOGGER.info("Memory Manager initialization complete")
        except Exception as exc:
            LOGGER.exception("Failed to initialize Memory Manager")
            raise MemoryManagerInitializationError(
                f"Failed to initialize Memory Manager: {exc}"
            ) from exc

    async def shutdown(self) -> None:
        """Gracefully shut down the memory manager and storage tiers."""

        if not self._initialized:
            LOGGER.warning("Memory Manager not initialized, nothing to shut down")
            return

        try:
            LOGGER.info("Shutting down Memory Manager")

            self._shutdown_event.set()

            drain_timeout = self._shutdown_drain_timeout
            wait_timeout = drain_timeout if drain_timeout > 0 else None

            if self._maintenance_task:
                try:
                    if wait_timeout is None:
                        await self._maintenance_task
                    else:
                        await asyncio.wait_for(
                            self._maintenance_task, timeout=wait_timeout
                        )
                except asyncio.TimeoutError:
                    LOGGER.warning(
                        "Timed out waiting for maintenance task to finish; cancelling",
                    )
                    self._maintenance_task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await self._maintenance_task
                except asyncio.CancelledError:
                    pass
                except Exception:
                    LOGGER.exception("Maintenance task raised during shutdown")
                finally:
                    self._maintenance_task = None
            self._maintenance_orchestrator = None

            try:
                await self._consolidation_guard.wait_for_all(timeout=wait_timeout)
            except asyncio.TimeoutError:
                LOGGER.warning(
                    "Timed out waiting for in-flight consolidations to finish during shutdown",
                )

            if self._stm:
                await self._stm.shutdown()

            if self._mtm:
                await self._mtm.shutdown()

            if self._ltm:
                await self._ltm.shutdown()

            self._initialized = False
            LOGGER.info("Memory Manager shutdown complete")
        except Exception as exc:
            LOGGER.exception("Failed to shut down Memory Manager")
            raise MemoryManagerOperationError(
                f"Failed to shut down Memory Manager: {exc}"
            ) from exc

    def _ensure_initialized(self) -> None:
        """Ensure that the Memory Manager is initialized."""

        if not self._initialized:
            raise MemoryManagerOperationError(
                "Memory Manager not initialized. Call initialize() first."
            )

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

    def _get_tier_by_name(
        self, tier_name: str
    ) -> ShortTermMemoryTier | MediumTermMemoryTier | LongTermMemoryTier:
        """Return a tier instance by canonical storage key."""

        normalized = self._normalize_tier_name(tier_name)
        if normalized == self.STM_TIER:
            if self._stm is None:
                raise MemoryManagerOperationError("STM storage tier not available")
            return self._stm
        if normalized == self.MTM_TIER:
            if self._mtm is None:
                raise MemoryManagerOperationError("MTM storage tier not available")
            return self._mtm
        if normalized == self.LTM_TIER:
            if self._ltm is None:
                raise MemoryManagerOperationError("LTM storage tier not available")
            return self._ltm

        raise InvalidTierError(f"Unknown tier: {tier_name}")

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
                log=LOGGER.getChild("manager.maintenance"),
            )
        return self._maintenance_orchestrator

    def _start_maintenance_task(self) -> None:
        """Start the background maintenance task."""

        self._ensure_maintenance_orchestrator()
        if self._maintenance_task is None or self._maintenance_task.done():
            self._shutdown_event.clear()
            self._maintenance_task = asyncio.create_task(self._maintenance_loop())

    async def _maintenance_loop(self) -> None:
        """Background task for periodically running maintenance on all tiers."""

        orchestrator = self._ensure_maintenance_orchestrator()
        base_interval = float(self._maintenance_interval)
        if base_interval <= 0:
            base_interval = orchestrator.min_interval

        delay = max(base_interval, orchestrator.min_interval)

        try:
            while not self._shutdown_event.is_set():
                with contextlib.suppress(asyncio.TimeoutError):
                    await asyncio.wait_for(
                        self._shutdown_event.wait(),
                        timeout=delay,
                    )
                    break
                result = await orchestrator.run_cycle(triggered_by="scheduler")
                if result.get("status") == "error":
                    LOGGER.error(
                        "Background maintenance cycle completed with errors: %s",
                        result.get("errors", []),
                    )
                else:
                    LOGGER.debug(
                        "Background maintenance cycle completed successfully"
                    )

                try:
                    await self._refresh_capacity_pressure()
                except Exception:  # noqa: BLE001
                    LOGGER.debug(
                        "Capacity pressure refresh failed after maintenance cycle",
                        exc_info=True,
                    )

                if self._shutdown_event.is_set():
                    break

                delay = orchestrator.compute_next_delay(base_interval)
        except asyncio.CancelledError:
            LOGGER.info("Maintenance task cancelled")
            raise
        except Exception as exc:
            LOGGER.exception("Unexpected error in maintenance loop: %s", exc)


__all__ = ["MemoryManagerLifecycleMixin"]
