"""Asynchronous metacognition utilities for monitoring and self-regulation."""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

from neuroca.core.enums import MemoryTier
from neuroca.core.health.dynamics import HealthState

from ._async_utils import call_async_or_sync, extract_content, extract_metadata, search_memories
from .goal_manager import GoalStatus  # Placeholder import for status references
from .planner import Plan

logger = logging.getLogger(__name__)


class MetacognitiveMonitor:
    """Monitor the system's internal state and performance asynchronously."""

    def __init__(
        self,
        health_manager: Any | None = None,
        memory_manager: Any | None = None,
        goal_manager: Any | None = None,
    ) -> None:
        logger.info("MetacognitiveMonitor initialized.")
        self.health_manager = health_manager
        self.memory_manager = memory_manager
        self.goal_manager = goal_manager
        self.last_error_log: list[dict[str, Any]] = []
        self.performance_metrics: dict[str, Any] = {
            "total_actions_completed": 0,
            "total_energy_consumed": 0.0,
            "avg_action_cost": 0.0,
        }
        self.max_error_log_size = 20

    async def log_error(self, error_details: dict[str, Any]) -> None:
        error_details["timestamp"] = error_details.get("timestamp", time.time())
        self.last_error_log.append(error_details)
        if len(self.last_error_log) > self.max_error_log_size:
            self.last_error_log.pop(0)

        logger.warning(
            "Metacognition logged error: %s: %s",
            error_details.get("type", "Unknown"),
            error_details.get("message", ""),
        )

        if not self.memory_manager:
            return

        mem_content = {
            "type": "error",
            "error_type": error_details.get("type", "Unknown"),
            "message": error_details.get("message", ""),
            "details": error_details,
        }
        tags = ["error", error_details.get("type", "unknown_error")]
        metadata = {
            "error_source": error_details.get("source", "unknown_component"),
            "component": error_details.get("component", "system"),
            "severity": error_details.get("severity", "warning"),
            "tags": tags,
        }
        if "task" in error_details:
            metadata["task"] = error_details["task"]
        if "action" in error_details:
            metadata["action"] = error_details["action"]

        store_methods = [
            ("add_memory", {
                "content": mem_content,
                "metadata": metadata,
                "tags": tags,
                "importance": 0.8,
                "initial_tier": MemoryTier.EPISODIC.storage_key,
            }),
            ("store", {
                "content": mem_content,
                "tier": MemoryTier.EPISODIC.canonical_label,
                "metadata": metadata,
            }),
        ]

        for method_name, kwargs in store_methods:
            method = getattr(self.memory_manager, method_name, None)
            if method is None:
                continue
            try:
                await call_async_or_sync(method, **kwargs)
            except TypeError:
                continue
            except Exception:  # noqa: BLE001
                logger.exception("Failed to store error in memory via %s", method_name)
            else:
                logger.debug("Error stored in episodic memory using %s", method_name)
                break

    def log_action_completion(self, action_cost: float) -> None:
        self.performance_metrics["total_actions_completed"] += 1
        self.performance_metrics["total_energy_consumed"] += action_cost
        total_actions = self.performance_metrics["total_actions_completed"]
        if total_actions > 0:
            self.performance_metrics["avg_action_cost"] = (
                self.performance_metrics["total_energy_consumed"] / total_actions
            )

    async def assess_current_state(self) -> dict[str, Any]:
        state_summary: dict[str, Any] = {"assessment_timestamp": time.time()}

        if self.health_manager:
            component_states = []
            total_energy = 0.0
            component_count = 0
            try:
                component_ids = list(self.health_manager._components.keys())  # type: ignore[attr-defined]
            except Exception:  # noqa: BLE001
                component_ids = []
            for comp_id in component_ids:
                comp_health = self.health_manager.get_component_health(comp_id)
                if not comp_health:
                    continue
                component_states.append(comp_health.state)
                energy_param = comp_health.get_parameter("energy") if hasattr(comp_health, "get_parameter") else None
                if energy_param:
                    total_energy += getattr(energy_param, "value", 0)
                    component_count += 1

            if any(state in {HealthState.CRITICAL, HealthState.IMPAIRED} for state in component_states):
                state_summary["overall_health"] = HealthState.CRITICAL.value
            elif any(state in {HealthState.STRESSED, HealthState.FATIGUED} for state in component_states):
                degraded = getattr(HealthState, "DEGRADED", HealthState.STRESSED)
                state_summary["overall_health"] = degraded.value
            else:
                healthy = getattr(HealthState, "HEALTHY", HealthState.NORMAL)
                state_summary["overall_health"] = healthy.value

            avg_energy = total_energy / component_count if component_count else 0.0
            state_summary["average_energy"] = round(avg_energy, 3)
            state_summary["health_state_counts"] = {
                state.value: component_states.count(state) for state in HealthState if state in component_states
            }

        if self.goal_manager:
            active_goals = self.goal_manager.get_active_goals()  # type: ignore[attr-defined]
            state_summary["active_goal_count"] = len(active_goals)
            state_summary["highest_priority_goal"] = active_goals[0].description if active_goals else None
            suspended = [g for g in getattr(self.goal_manager, "goals", {}).values() if g.status == GoalStatus.SUSPENDED]
            state_summary["suspended_goal_count"] = len(suspended)

        if self.memory_manager:
            stats = {}
            method = getattr(self.memory_manager, "get_system_stats", None)
            if method:
                try:
                    stats = await call_async_or_sync(method)
                except Exception:  # noqa: BLE001
                    logger.exception("Failed to retrieve system stats")
            elif hasattr(self.memory_manager, "get_stats"):
                try:
                    stats = await call_async_or_sync(self.memory_manager.get_stats)
                except Exception:  # noqa: BLE001
                    logger.exception("Failed to retrieve legacy memory stats")

            working_stats = stats.get("working_memory", {}) if isinstance(stats, dict) else {}
            size = working_stats.get("size", working_stats.get("count", 0))
            capacity = working_stats.get("capacity", 1) or 1
            state_summary["working_memory_load"] = round(size / capacity, 3)
            state_summary["working_memory_count"] = size

        state_summary["recent_errors_count"] = len(self.last_error_log)
        state_summary["total_actions_completed"] = self.performance_metrics.get("total_actions_completed", 0)
        state_summary["avg_action_cost"] = round(self.performance_metrics.get("avg_action_cost", 0.0), 3)

        logger.info("Current cognitive state assessment: %s", state_summary)
        return state_summary

    async def estimate_confidence(self, data: Any, source: str) -> float:
        base_confidence = 0.75
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

        if hasattr(data, "calculate_activation"):
            try:
                mem_confidence = max(0.1, min(1.0, data.calculate_activation() * 0.8 + 0.1))
            except Exception:  # noqa: BLE001
                mem_confidence = 0.5
        else:
            mem_confidence = 0.5
        metadata = getattr(data, "metadata", None)
        if metadata and isinstance(metadata, dict) and "confidence" in metadata:
            mem_confidence = (mem_confidence + metadata["confidence"]) / 2
        base_confidence = (base_confidence + mem_confidence) / 2

        state = await self.assess_current_state()
        health_state = state.get("overall_health", "healthy")
        health_factor = 1.0
        if health_state == "degraded":
            health_factor = 0.9
        elif health_state == "unhealthy":
            health_factor = 0.7

        final_confidence = max(0.0, min(1.0, base_confidence * health_factor))
        logger.debug(
            "Estimated confidence for data from '%s': %.2f",
            source,
            final_confidence,
        )
        return final_confidence

    async def select_strategy(
        self,
        task_description: str,
        available_strategies: list[str],
        context: Optional[dict[str, Any]] = None,
    ) -> Optional[str]:
        if not available_strategies:
            logger.warning("No strategies available for task '%s'.", task_description)
            return None

        context = dict(context or {})
        current_state = await self.assess_current_state()
        health_status = current_state.get("overall_health", "healthy")
        wm_load = current_state.get("working_memory_load", 0.0)

        past_success: dict[str, float] = {strategy: 0.5 for strategy in available_strategies}
        if self.memory_manager:
            for strategy in available_strategies:
                query = f"strategy {strategy} task {task_description}"
                try:
                    past_attempts = await search_memories(
                        self.memory_manager,
                        query=query,
                        limit=5,
                        tiers=[MemoryTier.EPISODIC],
                    )
                except Exception:  # noqa: BLE001
                    logger.debug("Failed retrieving past performance for strategy %s", strategy, exc_info=True)
                    continue
                if not past_attempts:
                    continue
                success_count = 0
                for item in past_attempts:
                    metadata = extract_metadata(item)
                    if metadata.get("outcome") == "success":
                        success_count += 1
                past_success[strategy] = success_count / len(past_attempts)

        strategy_scores: dict[str, float] = {}
        for strategy in available_strategies:
            score = 0.5
            if health_status == "healthy":
                if strategy == "detailed_planning":
                    score += 0.2
                if strategy == "systematic_search":
                    score += 0.1
            elif health_status == "degraded":
                if strategy in {"heuristic_search", "memory_retrieval"}:
                    score += 0.1
                if strategy == "detailed_planning":
                    score -= 0.2
            elif health_status == "unhealthy":
                if strategy == "simple_heuristic":
                    score += 0.3
                if strategy == "detailed_planning":
                    score -= 0.5

            if wm_load > 0.8 and strategy == "detailed_planning":
                score -= 0.3

            score += past_success.get(strategy, 0.5) * 0.3
            strategy_scores[strategy] = score

        best_strategy = max(strategy_scores, key=strategy_scores.get)
        logger.info(
            "Selected strategy '%s' for task '%s' (Score: %.2f, Health: %s, WM Load: %.2f). Scores: %s",
            best_strategy,
            task_description,
            strategy_scores[best_strategy],
            health_status,
            wm_load,
            strategy_scores,
        )
        return best_strategy

    async def detect_error_patterns(self, error_type: Optional[str] = None) -> dict[str, Any]:
        if not self.memory_manager:
            logger.warning("Cannot detect error patterns: Memory manager not available")
            return {"patterns_detected": False, "reason": "memory_unavailable"}

        query = "type:error"
        if error_type:
            query += f" error_type:{error_type}"

        try:
            error_memories = await search_memories(
                self.memory_manager,
                query=query,
                limit=20,
                tiers=[MemoryTier.EPISODIC],
            )
        except Exception:  # noqa: BLE001
            logger.exception("Error during pattern detection")
            return {"patterns_detected": False, "reason": "analysis_error"}

        if not error_memories:
            return {"patterns_detected": False, "reason": "no_errors_found"}

        patterns = {
            "total_errors": len(error_memories),
            "by_type": {},
            "by_component": {},
            "by_source": {},
            "common_sequences": [],
            "recent_errors": [],
        }

        for mem in error_memories:
            content = extract_content(mem)
            metadata = extract_metadata(mem)
            err_type = (content or {}).get("error_type", "unknown") if isinstance(content, dict) else "unknown"
            component = metadata.get("component", "unknown")
            source = metadata.get("error_source", "unknown")
            patterns["by_type"][err_type] = patterns["by_type"].get(err_type, 0) + 1
            patterns["by_component"][component] = patterns["by_component"].get(component, 0) + 1
            patterns["by_source"][source] = patterns["by_source"].get(source, 0) + 1

            if len(patterns["recent_errors"]) < 5:
                patterns["recent_errors"].append(
                    {
                        "type": err_type,
                        "message": (content or {}).get("message", "") if isinstance(content, dict) else "",
                        "component": component,
                        "timestamp": metadata.get("timestamp", 0),
                    }
                )

        patterns["most_common_type"] = max(patterns["by_type"], key=patterns["by_type"].get, default=None)
        patterns["most_common_component"] = max(
            patterns["by_component"], key=patterns["by_component"].get, default=None
        )
        patterns["patterns_detected"] = True
        return patterns

    async def optimize_resource_allocation(
        self,
        task_complexity: float,
        current_plan: Optional[Plan] = None,
        task_type: Optional[str] = None,
    ) -> dict[str, float]:
        state = await self.assess_current_state()
        health_status = state.get("overall_health", "healthy")

        allocation = {
            "energy_budget_factor": 1.0,
            "attention_focus_level": 0.8,
            "time_budget_factor": 1.0,
            "parallel_processes": 1,
        }

        if health_status == "degraded":
            allocation["energy_budget_factor"] = 0.7
            allocation["attention_focus_level"] = 0.6
            allocation["parallel_processes"] = 1
        elif health_status == "unhealthy":
            allocation["energy_budget_factor"] = 0.4
            allocation["attention_focus_level"] = 0.5
            allocation["time_budget_factor"] = 1.5

        if task_complexity > 0.7:
            allocation["attention_focus_level"] = min(1.0, allocation["attention_focus_level"] + 0.2)
            allocation["energy_budget_factor"] = min(1.0, allocation["energy_budget_factor"] + 0.1)
            allocation["time_budget_factor"] = 1.2

        if self.memory_manager and task_type:
            query = f"task_type:{task_type} complexity:{int(task_complexity * 10)}/10"
            try:
                similar_tasks = await search_memories(
                    self.memory_manager,
                    query=query,
                    limit=5,
                    tiers=[MemoryTier.EPISODIC],
                )
            except Exception:  # noqa: BLE001
                logger.debug("Failed retrieving past task memory for resource optimization", exc_info=True)
            else:
                if similar_tasks:
                    past_energy = []
                    past_attention = []
                    past_time = []
                    for task_mem in similar_tasks:
                        metadata = extract_metadata(task_mem)
                        resources = metadata.get("resources", {}) if isinstance(metadata, dict) else {}
                        if "energy_used" in resources:
                            past_energy.append(resources["energy_used"])
                        if "attention_level" in resources:
                            past_attention.append(resources["attention_level"])
                        if "time_taken" in resources:
                            past_time.append(resources["time_taken"])
                    if len(past_energy) >= 3:
                        allocation["energy_budget_factor"] = (
                            allocation["energy_budget_factor"] + (sum(past_energy) / len(past_energy))
                        ) / 2
                    if len(past_attention) >= 3:
                        allocation["attention_focus_level"] = (
                            allocation["attention_focus_level"] + (sum(past_attention) / len(past_attention))
                        ) / 2
                    if len(past_time) >= 3:
                        allocation["time_budget_factor"] = (
                            allocation["time_budget_factor"] + (sum(past_time) / len(past_time))
                        ) / 2

        if current_plan:
            plan_steps = len(getattr(current_plan, "steps", []))
            if plan_steps > 5 and health_status == "healthy":
                allocation["attention_focus_level"] = min(1.0, allocation["attention_focus_level"] + 0.1)
                allocation["parallel_processes"] = min(3, max(1, plan_steps // 3))

        for key in allocation:
            if key.endswith("_factor") or key == "attention_focus_level":
                allocation[key] = max(0.1, min(2.0, allocation[key]))
        allocation["parallel_processes"] = int(allocation["parallel_processes"])

        logger.info(
            "Suggested resource allocation: %s (Health: %s, Task Complexity: %.2f)",
            allocation,
            health_status,
            task_complexity,
        )
        return allocation
