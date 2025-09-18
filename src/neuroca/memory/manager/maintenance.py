from __future__ import annotations

import asyncio
import inspect
import logging
import time
import uuid
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, Iterable, List, Mapping, Optional, TYPE_CHECKING

from neuroca.memory.manager.decay import decay_ltm_memories, decay_mtm_memories

if TYPE_CHECKING:  # pragma: no cover - circular import guard
    from .memory_manager import MemoryManager
    from .events import MaintenanceEventPublisher


logger = logging.getLogger(__name__)


@dataclass
class MaintenanceTelemetry:
    """Rolling telemetry captured for the background maintenance scheduler."""

    cycles: int = 0
    successful_cycles: int = 0
    consecutive_failures: int = 0
    total_failures: int = 0
    last_started_at: float | None = None
    last_completed_at: float | None = None
    last_error: str | None = None

    def record(self, *, started_at: float, completed_at: float, errors: List[str]) -> None:
        """Update telemetry counters based on the outcome of a cycle."""

        self.cycles += 1
        self.last_started_at = started_at
        self.last_completed_at = completed_at

        if errors:
            self.total_failures += 1
            self.consecutive_failures += 1
            self.last_error = "; ".join(errors)
        else:
            self.successful_cycles += 1
            self.consecutive_failures = 0
            self.last_error = None

    @property
    def last_duration(self) -> float | None:
        """Return the duration of the most recent cycle if available."""

        if self.last_started_at is None or self.last_completed_at is None:
            return None
        return max(0.0, self.last_completed_at - self.last_started_at)

    def as_dict(self) -> Dict[str, Any]:
        """Serialise telemetry for reporting or metrics sinks."""

        return {
            "cycles": self.cycles,
            "successful_cycles": self.successful_cycles,
            "consecutive_failures": self.consecutive_failures,
            "total_failures": self.total_failures,
            "last_started_at": self.last_started_at,
            "last_completed_at": self.last_completed_at,
            "last_duration_seconds": self.last_duration,
            "last_error": self.last_error,
        }


class MaintenanceOrchestrator:
    """Coordinate tier maintenance, decay, cleanup, and consolidation."""

    def __init__(
        self,
        manager: "MemoryManager",
        *,
        min_interval: float = 30.0,
        telemetry_sink: Callable[[Dict[str, Any]], Awaitable[None] | None] | None = None,
        decay_handlers: Dict[str, Callable[[], Awaitable[Any]]] | None = None,
        log: Optional[logging.Logger] = None,
        event_publisher: "MaintenanceEventPublisher" | None = None,
    ) -> None:
        self._manager = manager
        self._min_interval = max(0.0, float(min_interval))
        self._telemetry_sink = telemetry_sink
        self._decay_handlers_override = decay_handlers
        self._log = log or logger.getChild("orchestrator")
        self._telemetry = MaintenanceTelemetry()
        self._lock = asyncio.Lock()
        self._event_publisher = event_publisher

    @property
    def telemetry(self) -> MaintenanceTelemetry:
        """Expose the current telemetry snapshot."""

        return self._telemetry

    @property
    def min_interval(self) -> float:
        """Return the minimum retry interval enforced by the orchestrator."""

        return self._min_interval

    def compute_next_delay(self, base_interval: float) -> float:
        """Compute the delay before the next run based on telemetry."""

        base = float(base_interval)
        if base <= 0:
            base = self._min_interval or 0.0

        if self._telemetry.consecutive_failures == 0:
            return max(base, self._min_interval)

        backoff_divisor = min(4, self._telemetry.consecutive_failures + 1)
        delay = base / backoff_divisor if base > 0 else self._min_interval
        return max(self._min_interval, delay)

    async def run_cycle(self, *, triggered_by: str) -> Dict[str, Any]:
        """Execute a maintenance cycle and return a structured report."""

        async with self._lock:
            started_at = time.time()
            errors: List[str] = []
            cycle_id = str(uuid.uuid4())
            report: Dict[str, Any] = {
                "cycle_id": cycle_id,
                "started_at": started_at,
                "triggered_by": triggered_by,
                "tiers": {},
                "cleanup": {},
                "decay": {},
                "consolidation": {
                    "stm_to_mtm": 0,
                    "mtm_to_ltm": 0,
                    "total": 0,
                },
                "errors": errors,
            }

            await self._publish_cycle_started(cycle_id, triggered_by)

            try:
                tier_results = await self._run_tier_maintenance(errors)
                if tier_results:
                    report["tiers"] = tier_results

                cleanup_results = await self._run_cleanup(errors)
                if cleanup_results:
                    report["cleanup"] = cleanup_results

                decay_results = await self._run_decay(errors)
                if decay_results:
                    report["decay"] = decay_results

                consolidation_results = await self._run_consolidation(errors)
                report["consolidation"] = consolidation_results
                report["consolidated_memories"] = consolidation_results.get("total", 0)

                quality_results = await self._run_quality_analysis(errors)
                if quality_results:
                    report["quality"] = quality_results

                drift_results = await self._run_drift_detection(
                    errors,
                    quality_report=quality_results if quality_results else None,
                )
                if drift_results:
                    report["drift"] = drift_results

                completed_at = time.time()
                report["completed_at"] = completed_at
                report["duration_seconds"] = max(0.0, completed_at - started_at)

                report["status"] = "error" if errors else "ok"

                telemetry_error = await self._emit_telemetry(report)
                if telemetry_error:
                    errors.append(telemetry_error)
                    report["status"] = "error"

                self._telemetry.record(
                    started_at=started_at,
                    completed_at=completed_at,
                    errors=errors,
                )
                report["telemetry"] = self._telemetry.as_dict()
            except Exception as exc:
                errors.append(f"cycle crashed: {exc}")
                completed_at = time.time()
                report["completed_at"] = completed_at
                report["duration_seconds"] = max(0.0, completed_at - started_at)
                report["status"] = "error"
                self._telemetry.record(
                    started_at=started_at,
                    completed_at=completed_at,
                    errors=errors,
                )
                report["telemetry"] = self._telemetry.as_dict()
                raise
            finally:
                await self._publish_cycle_completed(cycle_id, triggered_by, report)

            return report

    async def _emit_telemetry(self, payload: Dict[str, Any]) -> Optional[str]:
        """Send the payload to the optional telemetry sink."""

        if not self._telemetry_sink:
            return None

        try:
            result = self._telemetry_sink(payload)
            if inspect.isawaitable(result):
                await result
        except Exception as exc:  # noqa: BLE001 - telemetry must never raise
            self._log.exception("Telemetry sink failed during maintenance cycle")
            return f"telemetry sink failed: {exc}"
        return None

    async def _publish_cycle_started(self, cycle_id: str, triggered_by: str) -> None:
        """Emit a start event for the current maintenance cycle."""

        publisher = self._event_publisher
        if publisher is None:
            return

        try:
            await publisher.cycle_started(cycle_id=cycle_id, triggered_by=triggered_by)
        except Exception:  # pragma: no cover - defensive logging
            self._log.debug("Failed to publish maintenance start event", exc_info=True)

    async def _publish_cycle_completed(
        self, cycle_id: str, triggered_by: str, report: Dict[str, Any]
    ) -> None:
        """Emit a completion event summarising ``report``."""

        publisher = self._event_publisher
        if publisher is None:
            return

        try:
            await publisher.cycle_completed(
                cycle_id=cycle_id,
                triggered_by=triggered_by,
                report=report,
            )
        except Exception:  # pragma: no cover - defensive logging
            self._log.debug("Failed to publish maintenance completion event", exc_info=True)

    async def _run_tier_maintenance(self, errors: List[str]) -> Dict[str, Any]:
        results: Dict[str, Any] = {}
        for name, tier in self._iter_tiers():
            handler = getattr(tier, "run_maintenance", None)
            if not handler:
                continue

            try:
                results[name] = await handler()
            except Exception as exc:  # noqa: BLE001
                self._log.exception("Tier maintenance failed for %s", name)
                errors.append(f"tier:{name} maintenance failed: {exc}")
        return results

    async def _run_cleanup(self, errors: List[str]) -> Dict[str, Any]:
        results: Dict[str, Any] = {}
        for name, tier in self._iter_tiers():
            cleanup = getattr(tier, "cleanup", None)
            if not cleanup:
                continue

            try:
                removed = await cleanup()
            except Exception as exc:  # noqa: BLE001
                self._log.exception("Cleanup failed for %s", name)
                errors.append(f"cleanup:{name} failed: {exc}")
                continue

            results[name] = {"removed": removed}
        return results

    async def _run_quality_analysis(self, errors: List[str]) -> Dict[str, Any]:
        evaluator = getattr(self._manager, "evaluate_memory_quality", None)
        if evaluator is None or not callable(evaluator):
            return {}

        try:
            return await evaluator()
        except Exception as exc:  # noqa: BLE001 - quality checks must not abort cycles
            self._log.exception("Quality analysis failed during maintenance cycle")
            errors.append(f"quality analysis failed: {exc}")
            return {}

    async def _run_drift_detection(
        self,
        errors: List[str],
        *,
        quality_report: Mapping[str, Any] | None,
    ) -> Dict[str, Any]:
        detector = getattr(self._manager, "detect_embedding_drift", None)
        if detector is None or not callable(detector):
            return {}

        try:
            result = await detector(quality_report=quality_report)
        except Exception as exc:  # noqa: BLE001 - drift checks must not abort cycles
            self._log.exception("Embedding drift detection failed during maintenance cycle")
            errors.append(f"drift detection failed: {exc}")
            return {}

        return result or {}

    async def _run_decay(self, errors: List[str]) -> Dict[str, Any]:
        results: Dict[str, Any] = {}

        if self._decay_handlers_override is not None:
            for name, handler in self._decay_handlers_override.items():
                try:
                    payload = await handler()
                except Exception as exc:  # noqa: BLE001
                    self._log.exception("Decay handler %s failed", name)
                    errors.append(f"decay:{name} failed: {exc}")
                    continue

                if isinstance(payload, dict):
                    results[name] = {"status": "ok", **payload}
                else:
                    results[name] = {"status": "ok"}
            return results

        config = getattr(self._manager, "_config", {})
        mtm = getattr(self._manager, "_mtm", None)
        ltm = getattr(self._manager, "_ltm", None)

        if mtm is not None:
            try:
                mtm_stats = await decay_mtm_memories(mtm, config.get("mtm", {}))
            except Exception as exc:  # noqa: BLE001
                self._log.exception("MTM decay failed during maintenance")
                errors.append(f"decay:mtm failed: {exc}")
            else:
                results["mtm"] = {"status": "ok", **mtm_stats}

        if ltm is not None:
            try:
                ltm_stats = await decay_ltm_memories(ltm, config.get("ltm", {}))
            except Exception as exc:  # noqa: BLE001
                self._log.exception("LTM decay failed during maintenance")
                errors.append(f"decay:ltm failed: {exc}")
            else:
                results["ltm"] = {"status": "ok", **ltm_stats}

        return results

    async def _run_consolidation(self, errors: List[str]) -> Dict[str, int]:
        summary: Dict[str, Any] = {"stm_to_mtm": 0, "mtm_to_ltm": 0, "total": 0}
        manager = self._manager
        config = getattr(manager, "_config", {})
        maintenance_cfg = config.get("maintenance", {}) if isinstance(config, dict) else {}

        breaker_decision = None
        if hasattr(manager, "_evaluate_consolidation_breaker"):
            breaker_decision = manager._evaluate_consolidation_breaker(self._telemetry)

        if breaker_decision and breaker_decision.skip:
            self._log.warning(
                "Skipping consolidation due to circuit breaker: %s",
                breaker_decision.reason or "threshold exceeded",
            )
            details = breaker_decision.details or {}
            summary.update(
                {
                    "status": "circuit_open",
                    "skipped": {
                        "reason": breaker_decision.reason,
                        "opened_at": breaker_decision.opened_at,
                        "cooldown_expires_at": breaker_decision.cooldown_expires_at,
                        "queued_backlog": details.get("queued_backlog"),
                        "consecutive_failures": details.get("consecutive_failures"),
                    },
                }
            )
            return summary

        stm_batch_size = self._coerce_positive_int(
            maintenance_cfg.get(
                "stm_to_mtm_batch_size",
                config.get("consolidation_batch_size", 5),
            ),
            default=5,
        )
        mtm_batch_size = self._coerce_positive_int(
            maintenance_cfg.get("mtm_to_ltm_batch_size", 10),
            default=10,
        )

        adapter = getattr(manager, "_capacity_adapter", None)
        if adapter is not None:
            stm_batch_size = adapter.stm_batch_size(stm_batch_size)
            mtm_batch_size = adapter.mtm_batch_size(mtm_batch_size)

        timestamp = time.time()
        stm = getattr(manager, "_stm", None)
        mtm = getattr(manager, "_mtm", None)
        ltm = getattr(manager, "_ltm", None)

        if stm is not None and mtm is not None and stm_batch_size != 0:
            candidates = await self._collect_stm_candidates(
                stm,
                limit=stm_batch_size,
                errors=errors,
            )
            for memory in candidates:
                memory_id = self._extract_memory_id(memory)
                if not memory_id:
                    continue

                try:
                    new_id = await manager.consolidate_memory(
                        memory_id=memory_id,
                        source_tier=manager.STM_TIER,
                        target_tier=manager.MTM_TIER,
                        additional_metadata={
                            "consolidated": True,
                            "consolidation_timestamp": timestamp,
                        },
                    )
                except Exception as exc:  # noqa: BLE001
                    self._log.exception(
                        "Failed consolidating STM memory %s", memory_id
                    )
                    errors.append(f"consolidation:stm_to_mtm failed for {memory_id}: {exc}")
                    continue

                if new_id:
                    summary["stm_to_mtm"] += 1

        if mtm is not None and ltm is not None and mtm_batch_size != 0:
            try:
                promotion_candidates = await mtm.get_promotion_candidates(limit=mtm_batch_size)
            except Exception as exc:  # noqa: BLE001
                self._log.exception("Failed to fetch MTM promotion candidates")
                errors.append(f"consolidation:mtm candidate fetch failed: {exc}")
            else:
                for candidate in promotion_candidates[:mtm_batch_size]:
                    memory_id = self._extract_memory_id(candidate)
                    if not memory_id:
                        continue

                    try:
                        new_id = await manager.consolidate_memory(
                            memory_id=memory_id,
                            source_tier=manager.MTM_TIER,
                            target_tier=manager.LTM_TIER,
                            additional_metadata={
                                "consolidated": True,
                                "consolidation_timestamp": timestamp,
                            },
                        )
                    except Exception as exc:  # noqa: BLE001
                        self._log.exception(
                            "Failed consolidating MTM memory %s", memory_id
                        )
                        errors.append(f"consolidation:mtm_to_ltm failed for {memory_id}: {exc}")
                        continue

                    if new_id:
                        summary["mtm_to_ltm"] += 1

        summary["total"] = summary["stm_to_mtm"] + summary["mtm_to_ltm"]
        return summary

    async def _collect_stm_candidates(
        self,
        stm_tier: Any,
        *,
        limit: int,
        errors: List[str],
    ) -> List[Dict[str, Any]]:
        try:
            records = await stm_tier.query(
                filters={
                    "metadata.importance": {"$gt": 0.7},
                    "metadata.access_count": {"$gt": 5},
                },
                limit=limit,
            )
        except Exception as exc:  # noqa: BLE001
            self._log.exception("Failed to query STM for consolidation candidates")
            errors.append(f"consolidation:stm candidate fetch failed: {exc}")
            return []

        if not records:
            return []

        scored: List[tuple[float, Dict[str, Any]]] = []
        base_threshold = 0.6
        threshold = base_threshold
        adapter = getattr(self._manager, "_capacity_adapter", None)
        if adapter is not None:
            threshold = adapter.stm_priority_threshold(base_threshold)
        for record in records:
            if not isinstance(record, dict):
                continue

            metadata = record.get("metadata")
            if not isinstance(metadata, dict):
                metadata = {}
            importance = float(metadata.get("importance", 0.5))
            access_count = int(record.get("access_count", metadata.get("access_count", 0)))
            priority_score = importance * (0.5 + (0.5 * min(access_count, 10) / 10))
            if priority_score >= threshold:
                scored.append((priority_score, record))

        scored.sort(key=lambda item: item[0], reverse=True)
        return [record for _, record in scored[:limit]]

    def _iter_tiers(self) -> Iterable[tuple[str, Any]]:
        manager = self._manager
        for name in (manager.STM_TIER, manager.MTM_TIER, manager.LTM_TIER):
            tier = getattr(manager, f"_{name}", None)
            if tier is not None:
                yield name, tier

    @staticmethod
    def _extract_memory_id(memory: Any) -> Optional[str]:
        if isinstance(memory, dict):
            return memory.get("id")
        return getattr(memory, "id", None)

    @staticmethod
    def _coerce_positive_int(value: Any, *, default: int) -> int:
        try:
            candidate = int(value)
        except (TypeError, ValueError):
            return max(0, default)
        return max(0, candidate)


__all__ = ["MaintenanceOrchestrator", "MaintenanceTelemetry"]
