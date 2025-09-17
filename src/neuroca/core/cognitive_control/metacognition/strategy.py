"""Strategy evaluation utilities for metacognitive monitoring."""

from __future__ import annotations

import logging
from typing import Any, Iterable


class StrategySelector:
    """Score candidate strategies using contextual signals and past outcomes."""

    def __init__(self, memory_manager: Any | None, logger: logging.Logger | None = None) -> None:
        self._memory_manager = memory_manager
        self._logger = logger or logging.getLogger(__name__)

    def set_memory_manager(self, memory_manager: Any | None) -> None:
        self._memory_manager = memory_manager

    def select(self, strategies: Iterable[str], task_description: str, state_summary: dict[str, Any]) -> str | None:
        strategies = list(strategies)
        if not strategies:
            self._logger.warning("No strategies provided for task '%s'.", task_description)
            return None

        health_status = state_summary.get("overall_health", "healthy")
        wm_load = float(state_summary.get("working_memory_load", 0.0))
        success_rates = self._collect_success_rates(strategies, task_description)

        best_strategy: str | None = None
        best_score = float("-inf")
        for strategy in strategies:
            score = self._score_strategy(strategy, health_status, wm_load, success_rates.get(strategy, 0.5))
            if score > best_score:
                best_strategy = strategy
                best_score = score

        if best_strategy is None:
            self._logger.warning("No strategies could be scored for task '%s'.", task_description)
            return None

        self._logger.info(
            "Selected strategy '%s' for task '%s' (score=%.2f, health=%s, wm_load=%.2f)",
            best_strategy,
            task_description,
            best_score,
            health_status,
            wm_load,
        )
        return best_strategy

    def _collect_success_rates(self, strategies: list[str], task_description: str) -> dict[str, float]:
        rates = {strategy: 0.5 for strategy in strategies}
        if not self._memory_manager:
            return rates

        for strategy in strategies:
            try:
                past_attempts = self._memory_manager.retrieve(
                    query=f"strategy {strategy} task {task_description}",
                    memory_type="episodic",
                    limit=5,
                )
            except Exception as error:  # noqa: BLE001 - external dependency
                self._logger.warning(
                    "Error retrieving past performance for '%s': %s",
                    strategy,
                    error,
                )
                continue

            rates[strategy] = self._calculate_success_rate(past_attempts)
        return rates

    @staticmethod
    def _calculate_success_rate(past_attempts: Any) -> float:
        if not past_attempts:
            return 0.5

        successes = 0
        total = 0
        for item in past_attempts:
            metadata = getattr(item, "metadata", {}) or {}
            if metadata.get("outcome") == "success":
                successes += 1
            total += 1

        if total == 0:
            return 0.5
        return successes / total

    @staticmethod
    def _score_strategy(strategy: str, health_status: str, wm_load: float, success_rate: float) -> float:
        score = 0.5 + (success_rate * 0.3)
        score += StrategySelector._health_modifier(strategy, health_status)
        if wm_load > 0.8 and strategy == "detailed_planning":
            score -= 0.3
        return score

    @staticmethod
    def _health_modifier(strategy: str, health_status: str) -> float:
        status = (health_status or "").lower()
        if status in {"healthy", "optimal", "normal"}:
            if strategy == "detailed_planning":
                return 0.2
            if strategy == "systematic_search":
                return 0.1
        elif status == "degraded":
            if strategy in {"heuristic_search", "memory_retrieval"}:
                return 0.1
            if strategy == "detailed_planning":
                return -0.2
        elif status in {"unhealthy", "critical"}:
            if strategy == "simple_heuristic":
                return 0.3
            if strategy == "detailed_planning":
                return -0.5
        return 0.0
