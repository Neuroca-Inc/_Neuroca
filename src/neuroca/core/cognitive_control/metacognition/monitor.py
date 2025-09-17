"""Metacognition Component for NeuroCognitive Architecture (NCA)."""

from __future__ import annotations

import logging
from typing import Any, Iterable, Optional

from ..goal_manager import GoalStatus
from ..planner import Plan
from .confidence import ConfidenceEstimator
from .patterns import ErrorPatternAnalyser
from .resource import ResourceAllocator
from .state_assessment import StateAssessor
from .strategy import StrategySelector
from .tracking import ErrorTracker, PerformanceTracker

logger = logging.getLogger(__name__)


class MetacognitiveMonitor:
    """Monitor internal cognitive signals and coordinate adaptive responses."""

    def __init__(
        self,
        health_manager: Any | None = None,
        memory_manager: Any | None = None,
        goal_manager: Any | None = None,
        *,
        max_error_log_size: int = 20,
    ) -> None:
        logger.info("MetacognitiveMonitor initialized.")
        self._health_manager = health_manager
        self._memory_manager = memory_manager
        self._goal_manager = goal_manager

        self._error_tracker = ErrorTracker(memory_manager, max_entries=max_error_log_size, logger=logger)
        self._performance_tracker = PerformanceTracker()
        self._state_assessor = StateAssessor(
            health_manager=health_manager,
            goal_manager=goal_manager,
            goal_status_enum=GoalStatus,
            memory_manager=memory_manager,
            performance_tracker=self._performance_tracker,
            error_tracker=self._error_tracker,
            logger=logger,
        )
        self._confidence_estimator = ConfidenceEstimator(logger)
        self._strategy_selector = StrategySelector(memory_manager, logger)
        self._pattern_analyser = ErrorPatternAnalyser(memory_manager, logger)
        self._resource_allocator = ResourceAllocator(memory_manager, logger)

    # ------------------------------------------------------------------
    # Dependency accessors
    # ------------------------------------------------------------------
    @property
    def health_manager(self) -> Any | None:  # pragma: no cover - trivial
        return self._health_manager

    @health_manager.setter
    def health_manager(self, manager: Any | None) -> None:
        self._health_manager = manager
        self._state_assessor.update_dependencies(health_manager=manager)

    @property
    def goal_manager(self) -> Any | None:  # pragma: no cover - trivial
        return self._goal_manager

    @goal_manager.setter
    def goal_manager(self, manager: Any | None) -> None:
        self._goal_manager = manager
        self._state_assessor.update_dependencies(goal_manager=manager)

    @property
    def memory_manager(self) -> Any | None:  # pragma: no cover - trivial
        return self._memory_manager

    @memory_manager.setter
    def memory_manager(self, manager: Any | None) -> None:
        self._memory_manager = manager
        self._error_tracker.set_memory_manager(manager)
        self._state_assessor.update_dependencies(memory_manager=manager)
        self._strategy_selector.set_memory_manager(manager)
        self._pattern_analyser.set_memory_manager(manager)
        self._resource_allocator.set_memory_manager(manager)

    # ------------------------------------------------------------------
    # Exposed metrics
    # ------------------------------------------------------------------
    @property
    def performance_metrics(self) -> dict[str, float]:
        """Return a snapshot of performance counters."""

        return self._performance_tracker.snapshot()

    @property
    def last_error_log(self) -> list[dict[str, Any]]:
        """Return recent error records."""

        return self._error_tracker.recent()

    @property
    def max_error_log_size(self) -> int:
        return self._error_tracker.max_entries

    @max_error_log_size.setter
    def max_error_log_size(self, value: int) -> None:
        self._error_tracker.set_max_entries(value)

    # ------------------------------------------------------------------
    # Core behaviours
    # ------------------------------------------------------------------
    def log_error(self, error_details: dict[str, Any]) -> None:
        """Record an error and persist it for later analysis."""

        normalised = self._error_tracker.record(error_details)
        logger.warning(
            "Metacognition logged error: %s - %s",
            normalised.get("type", "Unknown"),
            normalised.get("message", ""),
        )
        self._error_tracker.persist(normalised)

    def log_action_completion(self, action_cost: float) -> None:
        """Log the completion of an action to update performance metrics."""

        self._performance_tracker.record_completion(action_cost)

    def assess_current_state(self) -> dict[str, Any]:
        """Assess the overall current cognitive state."""

        return self._state_assessor.assess()

    def estimate_confidence(self, data: Any, source: str) -> float:
        """Estimate the confidence level in a piece of data or a prediction."""

        state = self.assess_current_state()
        health_status = state.get("overall_health", "healthy")
        return self._confidence_estimator.estimate(data, source, health_status)

    def select_strategy(
        self,
        task_description: str,
        available_strategies: Iterable[str],
        context: Optional[dict[str, Any]] = None,  # noqa: ARG002 - maintained for compatibility
    ) -> Optional[str]:
        """Select the most appropriate cognitive strategy for a given task."""

        _ = context  # Explicitly ignore unused context while keeping signature stable
        state = self.assess_current_state()
        return self._strategy_selector.select(list(available_strategies), task_description, state)

    def detect_error_patterns(self, error_type: Optional[str] = None) -> dict[str, Any]:
        """Analyse past errors to detect recurring patterns and potential causes."""

        return self._pattern_analyser.detect(error_type)

    def optimize_resource_allocation(
        self,
        task_complexity: float,
        current_plan: Optional[Plan] = None,
        task_type: Optional[str] = None,
    ) -> dict[str, float]:
        """Suggest adjustments to resource allocation based on task context."""

        state = self.assess_current_state()
        return self._resource_allocator.suggest(
            task_complexity=task_complexity,
            state_summary=state,
            current_plan=current_plan,
            task_type=task_type,
        )
