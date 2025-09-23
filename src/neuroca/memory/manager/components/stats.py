"""Monitoring and maintenance helpers for the memory manager."""

from __future__ import annotations

import asyncio
import inspect
import time
from typing import Any, Dict, Mapping

from neuroca.memory.exceptions import MemoryManagerOperationError
from neuroca.memory.manager.circuit_breaker import CircuitBreakerDecision

from .base import LOGGER


class MemoryManagerStatsMixin:
    """Surface maintenance utilities and system statistics."""

    def _capture_backpressure_snapshot(self) -> dict[str, dict[str, int]] | None:
        """Return a snapshot of back-pressure state used for degradation guards."""

        controller = getattr(self, "_backpressure", None)
        if controller is None:
            return None

        try:
            return controller.snapshot()
        except Exception:  # pragma: no cover
            LOGGER.debug(
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
        except Exception:
            LOGGER.exception("Maintenance circuit breaker evaluation failed")
            return None

        return decision

    @property
    def consolidation_breaker_status(self) -> dict[str, Any] | None:
        """Expose the breaker status for monitoring surfaces."""

        breaker = getattr(self, "_consolidation_breaker", None)
        if breaker is None:
            return None
        return breaker.status()

    @staticmethod
    def _safe_signature(callable_obj: Any) -> inspect.Signature | None:
        """Return a best-effort signature for ``callable_obj`` or ``None`` if unavailable."""

        if not callable(callable_obj):
            return None

        try:
            return inspect.signature(callable_obj)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _is_signature_compatible(
        signature: inspect.Signature | None,
        args: tuple[Any, ...],
        kwargs: Mapping[str, Any],
    ) -> bool:
        """Return ``True`` when ``args``/``kwargs`` can be bound against ``signature``."""

        if signature is None:
            return True

        try:
            signature.bind_partial(*args, **kwargs)
        except TypeError:
            return False
        return True

    @staticmethod
    def _can_call_without_arguments(signature: inspect.Signature | None) -> bool:
        """Return ``True`` when ``signature`` can be invoked without supplying arguments."""

        if signature is None:
            return True

        return not any(
            parameter.kind
            in (
                inspect.Parameter.POSITIONAL_ONLY,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                inspect.Parameter.KEYWORD_ONLY,
            )
            and parameter.default is inspect._empty
            for parameter in signature.parameters.values()
        )

    async def _resolve_counter_value(
        self, counter: Any, tier_name: str
    ) -> float | None:
        """Invoke ``counter`` safely and coerce the result into a ``float`` if possible."""

        if not callable(counter):
            LOGGER.debug("Skipping non-callable count handler for %s tier", tier_name)
            return None

        current: Any
        try:
            current = counter()
        except TypeError as exc:
            LOGGER.debug(
                "Count handler for %s tier rejected invocation: %s",
                tier_name,
                exc,
                exc_info=True,
            )
            return None
        except Exception:
            LOGGER.debug(
                "Count handler for %s tier raised an unexpected exception",
                tier_name,
                exc_info=True,
            )
            return None

        try:
            if asyncio.iscoroutine(current):
                current = await current
            return float(current)
        except Exception:
            LOGGER.debug(
                "Unable to coerce utilisation count for %s tier into a float",
                tier_name,
                exc_info=True,
            )
            return None

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
                LOGGER.debug(
                    "Skipping non-callable count handler for %s tier", tier_name
                )
                continue

            signature = self._safe_signature(counter)
            if not self._can_call_without_arguments(signature):
                LOGGER.debug(
                    "Skipping count handler for %s tier due to unsupported signature: %s",
                    tier_name,
                    signature,
                )
                continue

            capacity = self._resolve_tier_capacity(tier_name, tier)
            if not capacity:
                adapter.observe(tier_name, 0.0)
                continue

            try:
                current_value = await self._resolve_counter_value(counter, tier_name)
                if current_value is None:
                    continue
            except Exception:
                LOGGER.debug(
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
                LOGGER.debug(
                    "Ignoring invalid max_capacity %r for %s tier", candidate, tier_name
                )

        candidate = getattr(tier, "capacity", None)
        try:
            if candidate is not None:
                capacity = int(candidate)
                if capacity > 0:
                    return capacity
        except (TypeError, ValueError):
            LOGGER.debug(
                "Ignoring invalid capacity %r for %s tier", candidate, tier_name
            )
        return None

    async def get_system_stats(self) -> Dict[str, Any]:
        """Get statistics about the memory system."""

        self._ensure_initialized()

        try:
            stats = {
                "timestamp": time.time(),
                "tiers": {},
                "working_memory": {
                    "size": len(self._working_memory),
                    "capacity": self._working_memory.capacity,
                },
            }

            for tier_name, tier_instance in [
                (self.STM_TIER, self._stm),
                (self.MTM_TIER, self._mtm),
                (self.LTM_TIER, self._ltm),
            ]:
                tier_stats = await tier_instance.get_stats()
                stats["tiers"][tier_name] = tier_stats

            total_memories = sum(
                tier_stats.get("total_memories", 0)
                for tier_stats in stats["tiers"].values()
            )

            stats["total_memories"] = total_memories

            return stats
        except Exception as exc:
            LOGGER.exception("Failed to get system stats")
            raise MemoryManagerOperationError(
                f"Failed to get system stats: {exc}"
            ) from exc

    async def run_maintenance(self) -> Dict[str, Any]:
        """Run maintenance tasks on the memory system."""

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
        except Exception:
            LOGGER.debug(
                "Capacity pressure refresh failed after manual maintenance",
                exc_info=True,
            )

        return result


__all__ = ["MemoryManagerStatsMixin"]
