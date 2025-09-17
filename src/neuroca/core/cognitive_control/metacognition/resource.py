"""Resource allocation heuristics for the metacognitive monitor."""

from __future__ import annotations

import logging
from typing import Any

from ..planner import Plan


class ResourceAllocator:
    """Provide resource allocation suggestions given contextual signals."""

    def __init__(self, memory_manager: Any | None, logger: logging.Logger | None = None) -> None:
        self._memory_manager = memory_manager
        self._logger = logger or logging.getLogger(__name__)

    def set_memory_manager(self, memory_manager: Any | None) -> None:
        self._memory_manager = memory_manager

    def suggest(
        self,
        *,
        task_complexity: float,
        state_summary: dict[str, Any],
        current_plan: Plan | None = None,
        task_type: str | None = None,
    ) -> dict[str, float]:
        allocation = self._default_allocation()
        health_status = state_summary.get("overall_health", "healthy")

        self._adjust_for_health(allocation, health_status)
        self._adjust_for_complexity(allocation, task_complexity)
        if task_type:
            self._incorporate_task_history(allocation, task_type, task_complexity)
        if current_plan:
            self._adjust_for_plan(allocation, current_plan, health_status)
        self._clamp(allocation)

        self._logger.info(
            "Suggested resource allocation: %s (Health: %s, Task Complexity: %.2f)",
            allocation,
            health_status,
            task_complexity,
        )
        return allocation

    @staticmethod
    def _default_allocation() -> dict[str, float]:
        return {
            "energy_budget_factor": 1.0,
            "attention_focus_level": 0.8,
            "time_budget_factor": 1.0,
            "parallel_processes": 1,
        }

    @staticmethod
    def _adjust_for_health(allocation: dict[str, float], health_status: str) -> None:
        status = (health_status or "").lower()
        if status == "degraded":
            allocation.update(
                {
                    "energy_budget_factor": 0.7,
                    "attention_focus_level": 0.6,
                    "parallel_processes": 1,
                }
            )
        elif status in {"unhealthy", "critical"}:
            allocation.update(
                {
                    "energy_budget_factor": 0.4,
                    "attention_focus_level": 0.5,
                    "time_budget_factor": 1.5,
                }
            )

    @staticmethod
    def _adjust_for_complexity(allocation: dict[str, float], task_complexity: float) -> None:
        if task_complexity > 0.7:
            allocation["attention_focus_level"] = min(1.0, allocation["attention_focus_level"] + 0.2)
            allocation["energy_budget_factor"] = min(1.0, allocation["energy_budget_factor"] + 0.1)
            allocation["time_budget_factor"] = max(allocation["time_budget_factor"], 1.2)

    def _incorporate_task_history(self, allocation: dict[str, float], task_type: str, task_complexity: float) -> None:
        if not self._memory_manager:
            return

        try:
            similar_tasks = self._memory_manager.retrieve(
                query=f"task_type:{task_type} complexity:{int(task_complexity * 10)}/10",
                memory_type="episodic",
                limit=5,
            )
        except Exception as error:  # noqa: BLE001 - storage layer is external
            self._logger.warning(
                "Error retrieving past task memory for resource optimization: %s",
                error,
            )
            return

        resources = [getattr(task, "metadata", {}).get("resources", {}) for task in similar_tasks or []]
        if not resources:
            return

        self._blend_resource_history(allocation, resources)

    @staticmethod
    def _blend_resource_history(allocation: dict[str, float], history: list[dict[str, Any]]) -> None:
        energy = [entry["energy_used"] for entry in history if "energy_used" in entry]
        attention = [entry["attention_level"] for entry in history if "attention_level" in entry]
        time_taken = [entry["time_taken"] for entry in history if "time_taken" in entry]

        if len(energy) >= 3:
            allocation["energy_budget_factor"] = (allocation["energy_budget_factor"] + sum(energy) / len(energy)) / 2
        if len(attention) >= 3:
            allocation["attention_focus_level"] = (allocation["attention_focus_level"] + sum(attention) / len(attention)) / 2
        if len(time_taken) >= 3:
            allocation["time_budget_factor"] = (allocation["time_budget_factor"] + sum(time_taken) / len(time_taken)) / 2

    @staticmethod
    def _adjust_for_plan(allocation: dict[str, float], current_plan: Plan, health_status: str) -> None:
        steps = getattr(current_plan, "steps", None)
        if not steps:
            return

        plan_steps = len(steps)
        if plan_steps <= 5:
            return

        allocation["attention_focus_level"] = min(1.0, allocation["attention_focus_level"] + 0.1)
        if (health_status or "").lower() in {"healthy", "optimal", "normal"}:
            allocation["parallel_processes"] = min(3, max(1, plan_steps // 3))

    @staticmethod
    def _clamp(allocation: dict[str, float]) -> None:
        for key, value in allocation.items():
            if key.endswith("_factor") or key == "attention_focus_level":
                allocation[key] = max(0.1, min(2.0, float(value)))
        allocation["parallel_processes"] = int(allocation["parallel_processes"])
