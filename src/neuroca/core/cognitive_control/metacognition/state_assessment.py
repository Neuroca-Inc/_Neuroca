"""Helpers for computing metacognitive state summaries."""

from __future__ import annotations

import logging
import time
from collections import Counter
from typing import Any, Mapping

from neuroca.core.health.dynamics import HealthState

from .tracking import ErrorTracker, PerformanceTracker


class StateAssessor:
    """Aggregate health, goal, memory, and performance signals."""

    def __init__(
        self,
        *,
        health_manager: Any | None,
        goal_manager: Any | None,
        goal_status_enum: Any | None,
        memory_manager: Any | None,
        performance_tracker: PerformanceTracker,
        error_tracker: ErrorTracker,
        logger: logging.Logger | None = None,
    ) -> None:
        self._health_manager = health_manager
        self._goal_manager = goal_manager
        self._goal_status_enum = goal_status_enum
        self._memory_manager = memory_manager
        self._performance_tracker = performance_tracker
        self._error_tracker = error_tracker
        self._logger = logger or logging.getLogger(__name__)

    def update_dependencies(
        self,
        *,
        health_manager: Any | None = None,
        goal_manager: Any | None = None,
        goal_status_enum: Any | None = None,
        memory_manager: Any | None = None,
    ) -> None:
        if health_manager is not None:
            self._health_manager = health_manager
        if goal_manager is not None:
            self._goal_manager = goal_manager
        if goal_status_enum is not None:
            self._goal_status_enum = goal_status_enum
        if memory_manager is not None:
            self._memory_manager = memory_manager

    def assess(self) -> dict[str, Any]:
        """Return a snapshot of the current metacognitive state."""

        summary: dict[str, Any] = {"assessment_timestamp": time.time()}
        summary.update(self._health_summary())
        summary.update(self._goal_summary())
        summary.update(self._memory_summary())
        summary.update(self._performance_summary())
        summary["recent_errors_count"] = len(self._error_tracker)
        self._logger.debug("Current cognitive state assessment: %s", summary)
        return summary

    def _health_summary(self) -> dict[str, Any]:
        if not self._health_manager:
            return {}

        component_ids = list(getattr(self._health_manager, "_components", {}).keys())
        states: list[HealthState] = []
        energies: list[float] = []
        for component_id in component_ids:
            try:
                component_health = self._health_manager.get_component_health(component_id)
            except Exception:  # noqa: BLE001 - health manager implementations may vary
                continue
            if not component_health:
                continue
            state = getattr(component_health, "state", None)
            if isinstance(state, HealthState):
                states.append(state)
            energy_param = getattr(component_health, "get_parameter", None)
            if callable(energy_param):
                energy = energy_param("energy")
                value = getattr(energy, "value", None)
                if isinstance(value, (int, float)):
                    energies.append(float(value))

        if not states and not energies:
            return {}

        counts = Counter(states)
        overall = self._resolve_overall_health(counts)
        average_energy = round(sum(energies) / len(energies), 3) if energies else 0.0

        return {
            "overall_health": overall,
            "average_energy": average_energy,
            "health_state_counts": {
                state.value: counts.get(state, 0)
                for state in HealthState
            },
        }

    @staticmethod
    def _resolve_overall_health(counts: Counter) -> str:
        if counts.get(HealthState.CRITICAL) or counts.get(HealthState.IMPAIRED):
            return HealthState.CRITICAL.value
        if counts.get(HealthState.STRESSED) or counts.get(HealthState.FATIGUED):
            degraded = getattr(HealthState, "DEGRADED", HealthState.STRESSED)
            return degraded.value
        healthy = getattr(HealthState, "HEALTHY", HealthState.NORMAL)
        return healthy.value

    def _goal_summary(self) -> dict[str, Any]:
        if not self._goal_manager:
            return {}

        try:
            active_goals = list(self._goal_manager.get_active_goals())
        except Exception:  # noqa: BLE001 - goal manager is external
            return {}

        suspended_count = 0
        goals_mapping = getattr(self._goal_manager, "goals", {})
        goal_status_cls = self._goal_status_enum
        suspended_value = getattr(goal_status_cls, "SUSPENDED", None)
        for goal in getattr(goals_mapping, "values", lambda: [])():
            status = getattr(goal, "status", None)
            if suspended_value is not None and status == suspended_value:
                suspended_count += 1

        return {
            "active_goal_count": len(active_goals),
            "highest_priority_goal": getattr(active_goals[0], "description", None) if active_goals else None,
            "suspended_goal_count": suspended_count,
        }

    def _memory_summary(self) -> dict[str, Any]:
        if not self._memory_manager:
            return {}

        try:
            stats = self._memory_manager.get_stats()
        except Exception:  # noqa: BLE001 - stats may not be implemented
            return {}

        working = stats.get("working_memory", {}) if isinstance(stats, Mapping) else {}
        utilization = working.get("utilization", 0)
        count = working.get("count", 0)

        return {
            "working_memory_load": round(float(utilization), 3),
            "working_memory_count": int(count),
        }

    def _performance_summary(self) -> dict[str, Any]:
        metrics = self._performance_tracker.snapshot()
        metrics["avg_action_cost"] = round(metrics["avg_action_cost"], 3)
        return metrics
