"""
Metacognition Component for NeuroCognitive Architecture (NCA).

This module implements metacognitive capabilities, allowing the system to
monitor, evaluate, and regulate its own cognitive processes.

Key functionalities:
- Self-monitoring: Tracking performance, errors, and resource usage.
- Confidence Estimation: Assessing the certainty of knowledge or predictions.
- Resource Allocation Optimization: Adjusting cognitive effort based on task demands and internal state.
- Strategy Selection: Choosing appropriate cognitive strategies for tasks.
"""

import logging
import time
from typing import Any, Optional

from neuroca.core.health.dynamics import (  # Example
    HealthState,
)
from neuroca.memory.models.memory_item import MemoryItem

from .goal_manager import GoalStatus  # Example, Import GoalStatus

# Import necessary components for potential integration
from .planner import Plan  # Import Plan for type hinting

# Configure logger
logger = logging.getLogger(__name__)

class MetacognitiveMonitor:
    """
    Monitors the system's internal state and performance.
    """
    def __init__(self, health_manager=None, memory_manager=None, goal_manager=None):
        """
        Initialize the MetacognitiveMonitor.

        Args:
            health_manager: Instance of HealthDynamicsManager.
            memory_manager: Instance of MemoryManager.
            goal_manager: Instance of GoalManager.
        """
        logger.info("MetacognitiveMonitor initialized.")
        self.health_manager = health_manager
        self.memory_manager = memory_manager
        self.goal_manager = goal_manager
        # NOTE: Consider implementing a proper dependency injection framework
        # for managing manager instances instead of direct constructor passing.
        self.last_error_log: list[dict] = [] # Simple error tracking, limited size
        self.performance_metrics: dict[str, Any] = { # Store more performance data
             "total_actions_completed": 0,
             "total_energy_consumed": 0.0,
             "avg_action_cost": 0.0,
        }
        self.max_error_log_size = 20

    def log_error(self, error_details: dict[str, Any]) -> None:
        """Record an error and persist it for later analysis."""

        normalized = self._normalise_error_details(error_details)
        self._remember_recent_error(normalized)
        logger.warning(
            "Metacognition logged error: %s - %s",
            normalized.get("type", "Unknown"),
            normalized.get("message", ""),
        )
        self._persist_error_memory(normalized)

    def _normalise_error_details(self, error_details: dict[str, Any]) -> dict[str, Any]:
        """Ensure the error payload contains the core fields used downstream."""

        normalised = dict(error_details)
        normalised.setdefault("timestamp", time.time())
        normalised.setdefault("type", "Unknown")
        normalised.setdefault("message", "")
        return normalised

    def _remember_recent_error(self, error_details: dict[str, Any]) -> None:
        """Maintain a bounded list of recent errors for quick inspection."""

        self.last_error_log.append(error_details)
        if len(self.last_error_log) > self.max_error_log_size:
            self.last_error_log.pop(0)

    def _persist_error_memory(self, error_details: dict[str, Any]) -> None:
        """Persist an error entry to episodic memory if a manager is available."""

        if not self.memory_manager:
            return

        content, metadata = self._build_error_memory_payload(error_details)
        try:
            self.memory_manager.store(
                content=content,
                memory_type="episodic",
                metadata=metadata,
                emotional_salience=0.8,
            )
            logger.debug("Error stored in episodic memory: %s", error_details.get("type", "Unknown"))
        except Exception as error:  # noqa: BLE001 - defensive guard
            logger.error("Failed to store error in memory: %s", error)

    @staticmethod
    def _build_error_memory_payload(error_details: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        """Create the content and metadata payload used for memory storage."""

        content = {
            "type": "error",
            "error_type": error_details.get("type", "Unknown"),
            "message": error_details.get("message", ""),
            "details": error_details,
        }
        metadata = {
            "error_source": error_details.get("source", "unknown_component"),
            "component": error_details.get("component", "system"),
            "severity": error_details.get("severity", "warning"),
            "tags": ["error", error_details.get("type", "unknown_error")],
        }

        for key in ("task", "action"):
            if key in error_details:
                metadata[key] = error_details[key]

        return content, metadata

    def log_action_completion(self, action_cost: float):
         """Log the completion of an action to update performance metrics."""
         self.performance_metrics["total_actions_completed"] += 1
         self.performance_metrics["total_energy_consumed"] += action_cost
         total_actions = self.performance_metrics["total_actions_completed"]
         if total_actions > 0:
              self.performance_metrics["avg_action_cost"] = self.performance_metrics["total_energy_consumed"] / total_actions

    def assess_current_state(self) -> dict[str, Any]:
        """
        Assess the overall current state of the cognitive system, including performance.

        Returns:
            A dictionary summarizing the current state (e.g., health, goals, memory, performance).
        """
        logger.debug("Assessing current cognitive state.")
        state_summary = {"assessment_timestamp": time.time()}

        # 1. Health Summary
        if self.health_manager:
            all_component_ids = list(self.health_manager._components.keys()) # Direct access for example
            component_states = []
            total_energy = 0.0
            component_count = 0
            for comp_id in all_component_ids:
                comp_health = self.health_manager.get_component_health(comp_id)
                if comp_health:
                    component_states.append(comp_health.state)
                    energy_param = comp_health.get_parameter("energy")
                    if energy_param:
                        total_energy += energy_param.value
                        component_count += 1
            
            # Determine overall status
            if HealthState.CRITICAL in component_states or HealthState.IMPAIRED in component_states:
                state_summary["overall_health"] = HealthState.CRITICAL.value # Use most severe
            elif HealthState.STRESSED in component_states or HealthState.FATIGUED in component_states:
                state_summary["overall_health"] = HealthState.DEGRADED.value if hasattr(HealthState, 'DEGRADED') else HealthState.STRESSED.value # Use representative degraded state
            else:
                 state_summary["overall_health"] = HealthState.HEALTHY.value if hasattr(HealthState, 'HEALTHY') else HealthState.NORMAL.value # Default healthy state name
            
            state_summary["average_energy"] = round((total_energy / component_count), 3) if component_count > 0 else 0.0
            # Add counts of specific states
            state_summary["health_state_counts"] = {state.value: component_states.count(state) for state in HealthState}

        # 2. Goal Summary
        if self.goal_manager:
            active_goals = self.goal_manager.get_active_goals()
            state_summary["active_goal_count"] = len(active_goals)
            state_summary["highest_priority_goal"] = active_goals[0].description if active_goals else None
            state_summary["suspended_goal_count"] = len([g for g in self.goal_manager.goals.values() if g.status == GoalStatus.SUSPENDED])

        # 3. Memory Load Summary
        if self.memory_manager:
             stats = self.memory_manager.get_stats()
             wm_stats = stats.get("working_memory", {})
             state_summary["working_memory_load"] = round(wm_stats.get("utilization", 0), 3)
             state_summary["working_memory_count"] = wm_stats.get("count", 0)

        # 4. Performance & Error Summary
        state_summary["recent_errors_count"] = len(self.last_error_log)
        state_summary["total_actions_completed"] = self.performance_metrics.get("total_actions_completed", 0)
        state_summary["avg_action_cost"] = round(self.performance_metrics.get("avg_action_cost", 0.0), 3)

        logger.info(f"Current cognitive state assessment: {state_summary}")
        return state_summary

    def estimate_confidence(self, data: Any, source: str) -> float:
        """
        Estimate the confidence level in a piece of data or a prediction.

        Args:
            data: The data item (e.g., retrieved memory, prediction).
            source: The source of the data (e.g., "semantic_memory", "llm_prediction").

        Returns:
            A confidence score (e.g., 0.0 to 1.0).
        """
        # --- Enhanced Placeholder Confidence Estimation Logic ---
        base_confidence = 0.75 # Default

        # 1. Source Reliability
        if source == "semantic_memory":
            base_confidence = 0.85
        elif source == "episodic_memory":
            base_confidence = 0.70
        elif source == "working_memory":
            base_confidence = 0.65
        elif source == "llm_prediction":
            base_confidence = 0.60
        elif source == "direct_input":
             base_confidence = 0.90

        # 2. Data Specifics (if applicable)
        if isinstance(data, MemoryItem):
             # Combine source reliability with memory activation/metadata
             mem_confidence = max(0.1, min(1.0, data.calculate_activation() * 0.8 + 0.1))
             if "confidence" in data.metadata:
                 mem_confidence = (mem_confidence + data.metadata["confidence"]) / 2
             base_confidence = (base_confidence + mem_confidence) / 2 # Average base and memory-specific
        # Could add checks for consistency with other knowledge here using memory_manager

        # 3. Health State Adjustment
        health_state = self.assess_current_state().get("overall_health", "healthy") # Get current assessment
        health_factor = 1.0
        if health_state == "degraded":
            health_factor = 0.9
        elif health_state == "unhealthy":
            health_factor = 0.7
        
        final_confidence = max(0.0, min(1.0, base_confidence * health_factor))

        logger.debug(f"Estimated confidence for data from '{source}': {final_confidence:.2f} (Base: {base_confidence:.2f}, HealthFactor: {health_factor:.2f})")
        return final_confidence
        # --- End Enhanced Placeholder ---

    def select_strategy(
        self,
        task_description: str,
        available_strategies: list[str],
        context: Optional[dict[str, Any]] = None,
    ) -> Optional[str]:
        """Select the most appropriate cognitive strategy for a given task."""

        if not available_strategies:
            logger.warning("No strategies provided for task '%s'.", task_description)
            return None

        context = context or {}
        current_state = self.assess_current_state()
        health_status = current_state.get("overall_health", "healthy")
        wm_load = current_state.get("working_memory_load", 0.0)
        success_rates = self._collect_strategy_success_rates(available_strategies, task_description)

        scores = {
            strategy: self._score_strategy(
                strategy,
                health_status,
                wm_load,
                success_rates.get(strategy, 0.5),
            )
            for strategy in available_strategies
        }

        if not scores:
            logger.warning("No strategies could be scored for task '%s'.", task_description)
            return None

        best_strategy = max(scores, key=scores.get)
        logger.info(
            "Selected strategy '%s' for task '%s' (score=%.2f, health=%s, wm_load=%.2f)",
            best_strategy,
            task_description,
            scores[best_strategy],
            health_status,
            wm_load,
        )
        return best_strategy

    def _collect_strategy_success_rates(
        self,
        strategies: list[str],
        task_description: str,
    ) -> dict[str, float]:
        """Gather empirical success rates for the available strategies."""

        default_rate = 0.5
        rates = {strategy: default_rate for strategy in strategies}
        if not self.memory_manager:
            return rates

        for strategy in strategies:
            try:
                past_attempts = self.memory_manager.retrieve(
                    query=f"strategy {strategy} task {task_description}",
                    memory_type="episodic",
                    limit=5,
                )
            except Exception as error:  # noqa: BLE001 - external dependency safety net
                logger.warning("Error retrieving past performance for '%s': %s", strategy, error)
                continue

            rates[strategy] = self._calculate_success_rate(past_attempts)
        return rates

    @staticmethod
    def _calculate_success_rate(past_attempts: Optional[list[Any]]) -> float:
        """Calculate the success rate from memory records."""

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

    def _score_strategy(
        self,
        strategy: str,
        health_status: str,
        wm_load: float,
        success_rate: float,
    ) -> float:
        """Combine contextual factors into a single score for a strategy."""

        score = 0.5 + (success_rate * 0.3)
        score += self._health_strategy_modifier(strategy, health_status)
        if wm_load > 0.8 and strategy == "detailed_planning":
            score -= 0.3
        return score

    @staticmethod
    def _health_strategy_modifier(strategy: str, health_status: str) -> float:
        """Health-specific adjustments used during strategy scoring."""

        if health_status == "healthy":
            if strategy == "detailed_planning":
                return 0.2
            if strategy == "systematic_search":
                return 0.1
        elif health_status == "degraded":
            if strategy in {"heuristic_search", "memory_retrieval"}:
                return 0.1
            if strategy == "detailed_planning":
                return -0.2
        elif health_status == "unhealthy":
            if strategy == "simple_heuristic":
                return 0.3
            if strategy == "detailed_planning":
                return -0.5
        return 0.0

    def detect_error_patterns(self, error_type: Optional[str] = None) -> dict[str, Any]:
        """Analyze past errors to detect recurring patterns and potential causes."""

        if not self.memory_manager:
            logger.warning("Cannot detect error patterns: Memory manager not available")
            return {"patterns_detected": False, "reason": "memory_unavailable"}

        try:
            error_memories = self._retrieve_error_memories(error_type)
        except Exception as error:  # noqa: BLE001 - protect against backend failures
            logger.error("Error during pattern detection: %s", error)
            return {"patterns_detected": False, "reason": f"analysis_error: {error}"}

        if not error_memories:
            return {"patterns_detected": False, "reason": "no_errors_found"}

        patterns = self._initialise_error_pattern_summary(error_memories)
        for memory in error_memories:
            self._update_error_pattern_counts(patterns, memory)
        self._finalise_error_patterns(patterns)
        return patterns

    def optimize_resource_allocation(
        self,
        task_complexity: float,
        current_plan: Optional[Plan] = None,
        task_type: Optional[str] = None,
    ) -> dict[str, float]:
        """Suggest adjustments to resource allocation based on task context."""

        logger.debug("Optimizing resource allocation for task complexity %.2f", task_complexity)
        state = self.assess_current_state()
        health_status = state.get("overall_health", "healthy")
        allocation = self._default_allocation()

        self._adjust_for_health_and_complexity(allocation, health_status, task_complexity)
        if task_type:
            self._incorporate_task_history(allocation, task_type, task_complexity)
        self._adjust_for_plan_characteristics(allocation, current_plan, health_status)
        self._clamp_allocation(allocation)

        logger.info(
            "Suggested resource allocation: %s (Health: %s, Task Complexity: %.2f)",
            allocation,
            health_status,
            task_complexity,
        )
        return allocation

    def _retrieve_error_memories(self, error_type: Optional[str]) -> list[Any]:
        query = "type:error"
        if error_type:
            query += f" error_type:{error_type}"

        return self.memory_manager.retrieve(
            query=query,
            memory_type="episodic",
            limit=20,
            sort_by="timestamp",
            sort_order="descending",
        )

    @staticmethod
    def _initialise_error_pattern_summary(error_memories: list[Any]) -> dict[str, Any]:
        return {
            "total_errors": len(error_memories),
            "by_type": {},
            "by_component": {},
            "by_source": {},
            "recent_errors": [],
        }

    @staticmethod
    def _update_error_pattern_counts(patterns: dict[str, Any], memory: Any) -> None:
        content = getattr(memory, "content", {}) or {}
        metadata = getattr(memory, "metadata", {}) or {}
        error_type = content.get("error_type", "unknown")
        component = metadata.get("component", "unknown")
        source = metadata.get("error_source", "unknown")

        patterns["by_type"][error_type] = patterns["by_type"].get(error_type, 0) + 1
        patterns["by_component"][component] = patterns["by_component"].get(component, 0) + 1
        patterns["by_source"][source] = patterns["by_source"].get(source, 0) + 1

        if len(patterns["recent_errors"]) < 5:
            patterns["recent_errors"].append(
                {
                    "type": error_type,
                    "message": content.get("message", ""),
                    "component": component,
                    "timestamp": metadata.get("timestamp", 0),
                }
            )

    @staticmethod
    def _finalise_error_patterns(patterns: dict[str, Any]) -> None:
        by_type = patterns.get("by_type", {})
        by_component = patterns.get("by_component", {})
        patterns["most_common_type"] = max(by_type, key=by_type.get, default=None)
        patterns["most_common_component"] = max(by_component, key=by_component.get, default=None)
        patterns["patterns_detected"] = True

    @staticmethod
    def _default_allocation() -> dict[str, float]:
        return {
            "energy_budget_factor": 1.0,
            "attention_focus_level": 0.8,
            "time_budget_factor": 1.0,
            "parallel_processes": 1,
        }

    def _adjust_for_health_and_complexity(
        self,
        allocation: dict[str, float],
        health_status: str,
        task_complexity: float,
    ) -> None:
        if health_status == "degraded":
            allocation.update(
                {
                    "energy_budget_factor": 0.7,
                    "attention_focus_level": 0.6,
                    "parallel_processes": 1,
                }
            )
        elif health_status == "unhealthy":
            allocation.update(
                {
                    "energy_budget_factor": 0.4,
                    "attention_focus_level": 0.5,
                    "time_budget_factor": 1.5,
                }
            )

        if task_complexity > 0.7:
            allocation["attention_focus_level"] = min(1.0, allocation["attention_focus_level"] + 0.2)
            allocation["energy_budget_factor"] = min(1.0, allocation["energy_budget_factor"] + 0.1)
            allocation["time_budget_factor"] = max(allocation["time_budget_factor"], 1.2)

    def _incorporate_task_history(
        self,
        allocation: dict[str, float],
        task_type: str,
        task_complexity: float,
    ) -> None:
        if not self.memory_manager:
            return

        try:
            similar_tasks = self.memory_manager.retrieve(
                query=f"task_type:{task_type} complexity:{int(task_complexity * 10)}/10",
                memory_type="episodic",
                limit=5,
            )
        except Exception as error:  # noqa: BLE001 - memory lookups may fail
            logger.warning("Error retrieving past task memory for resource optimization: %s", error)
            return

        history = [getattr(task, "metadata", {}).get("resources", {}) for task in similar_tasks or []]
        if not history:
            return

        self._average_resource_history(allocation, history)

    @staticmethod
    def _average_resource_history(allocation: dict[str, float], history: list[dict[str, Any]]) -> None:
        energy = [entry["energy_used"] for entry in history if "energy_used" in entry]
        attention = [entry["attention_level"] for entry in history if "attention_level" in entry]
        time_factors = [entry["time_taken"] for entry in history if "time_taken" in entry]

        if len(energy) >= 3:
            allocation["energy_budget_factor"] = (allocation["energy_budget_factor"] + sum(energy) / len(energy)) / 2
        if len(attention) >= 3:
            allocation["attention_focus_level"] = (allocation["attention_focus_level"] + sum(attention) / len(attention)) / 2
        if len(time_factors) >= 3:
            allocation["time_budget_factor"] = (allocation["time_budget_factor"] + sum(time_factors) / len(time_factors)) / 2

    @staticmethod
    def _adjust_for_plan_characteristics(
        allocation: dict[str, float],
        current_plan: Optional[Plan],
        health_status: str,
    ) -> None:
        if not current_plan or not hasattr(current_plan, "steps"):
            return

        plan_steps = len(current_plan.steps)
        if plan_steps <= 5:
            return

        allocation["attention_focus_level"] = min(1.0, allocation["attention_focus_level"] + 0.1)
        if health_status == "healthy":
            allocation["parallel_processes"] = min(3, max(1, plan_steps // 3))

    @staticmethod
    def _clamp_allocation(allocation: dict[str, float]) -> None:
        for key, value in allocation.items():
            if key.endswith("_factor") or key == "attention_focus_level":
                allocation[key] = max(0.1, min(2.0, value))
        allocation["parallel_processes"] = int(allocation["parallel_processes"])
