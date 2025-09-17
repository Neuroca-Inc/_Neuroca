"""
Decision Making Component for NeuroCognitive Architecture (NCA).

This module implements decision-making processes within the executive functions.
It evaluates potential actions or plans based on current goals, context,
predicted outcomes, resource availability (health/memory), and learned heuristics.

Key functionalities:
- Evaluating options against goals and constraints.
- Selecting the most appropriate action or plan.
- Incorporating uncertainty and risk assessment.
- Learning from past decision outcomes.
"""

import logging
from typing import Any, Optional

from neuroca.core.enums import MemoryTier  # Import the correct enum

# Import necessary components for potential integration
# from neuroca.memory.manager import MemoryManager # Example
from neuroca.core.health.dynamics import HealthState  # Example for context checking
from neuroca.core.models import MemoryItem  # Import MemoryItem

# Assuming Plan and PlanStep might be used or adapted for decision options

# from .goal_manager import GoalManager, Goal # Example

# Configure logger
logger = logging.getLogger(__name__)

class DecisionOption:
    """Represents a potential choice or action to be evaluated."""
    def __init__(self, description: str, action: Any, estimated_utility: float = 0.0, risk: float = 0.0):
        self.description = description
        self.action = action # Could be a PlanStep, a full Plan, or another representation
        self.estimated_utility = estimated_utility # Expected value/benefit
        self.risk = risk # Potential negative outcome probability/severity

class DecisionMaker:
    """
    Evaluates options and selects actions based on goals and context.

    Integrates with memory, health, and planning components to make informed
    and adaptive decisions.
    """
    def __init__(self, memory_manager=None, health_manager=None, planner=None, goal_manager=None):
        """
        Initialize the DecisionMaker.

        Args:
            memory_manager: Instance of MemoryManager.
            health_manager: Instance of HealthDynamicsManager.
            planner: Instance of Planner.
            goal_manager: Instance of GoalManager.
        """
        logger.info("DecisionMaker initialized.")
        self.memory_manager = memory_manager
        self.health_manager = health_manager
        self.planner = planner
        self.goal_manager = goal_manager
        # NOTE: Consider implementing a proper dependency injection framework
        # for managing manager instances instead of direct constructor passing.

    def choose_action(
        self,
        options: list[DecisionOption],
        context: Optional[dict[str, Any]] = None,
    ) -> Optional[DecisionOption]:
        """Select the best action from a list of options."""

        if not options:
            logger.warning("No options provided for decision making.")
            return None

        context = context or {}
        health_state = self._resolve_health_state(context)
        risk_aversion = self._risk_aversion_for_health(health_state)
        goal_description = self._resolve_goal_description(context)

        logger.info(
            "Evaluating %s options (health=%s, goal=%s).",
            len(options),
            getattr(health_state, "value", health_state),
            goal_description,
        )

        best_option: Optional[DecisionOption] = None
        best_score = -float("inf")

        for option in options:
            adjusted_utility = self._evaluate_option(
                option,
                goal_description,
                risk_aversion,
            )
            if adjusted_utility > best_score:
                best_option = option
                best_score = adjusted_utility

        if not best_option:
            logger.warning("Could not select a suitable option.")
            return None

        logger.info(
            "Selected option '%s' with adjusted utility %.2f.",
            best_option.description,
            best_score,
        )
        self._maybe_generate_subplan(best_option, context)
        return best_option

    def _resolve_goal_description(self, context: dict[str, Any]) -> str:
        """Determine the most relevant goal description for the current decision."""

        if "goal_description" in context and context["goal_description"]:
            return str(context["goal_description"]).strip()

        if self.goal_manager and hasattr(self.goal_manager, "get_highest_priority_active_goal"):
            try:
                active_goal = self.goal_manager.get_highest_priority_active_goal()
                if active_goal and getattr(active_goal, "description", None):
                    return str(active_goal.description)
            except Exception:  # noqa: BLE001 - guard against external implementations
                logger.debug("Goal manager unavailable for resolving goal description.")

        return "default_goal"

    @staticmethod
    def _resolve_health_state(context: dict[str, Any]) -> HealthState:
        """Extract the health state from the provided context."""

        value = context.get("health_state", HealthState.NORMAL)
        return value if isinstance(value, HealthState) else HealthState.NORMAL

    @staticmethod
    def _risk_aversion_for_health(health_state: HealthState) -> float:
        """Map health state to a risk aversion coefficient."""

        match health_state:
            case HealthState.STRESSED:
                return 0.8
            case HealthState.IMPAIRED | HealthState.CRITICAL:
                return 1.0
            case HealthState.OPTIMAL:
                return 0.3
            case _:
                return 0.5

    def _evaluate_option(
        self,
        option: DecisionOption,
        current_goal: str,
        risk_aversion: float,
    ) -> float:
        """Calculate the adjusted utility for an individual option."""

        base_utility = option.estimated_utility
        goal_bonus = self._goal_alignment_bonus(option.description, current_goal)
        past_outcome_adjustment = self._past_outcome_adjustment(option)
        adjusted = base_utility + goal_bonus + past_outcome_adjustment - (risk_aversion * option.risk)

        logger.debug(
            "Option '%s': base=%.2f goal_bonus=%.2f past_adj=%.2f risk=%.2f final=%.2f",
            option.description,
            base_utility,
            goal_bonus,
            past_outcome_adjustment,
            option.risk,
            adjusted,
        )
        return adjusted

    @staticmethod
    def _goal_alignment_bonus(description: str, current_goal: str) -> float:
        """Provide a simple alignment bonus when the option relates to the goal."""

        if current_goal and current_goal.lower() in description.lower():
            return 0.2
        return 0.0

    def _past_outcome_adjustment(self, option: DecisionOption) -> float:
        """Adjust utility based on historical outcomes stored in memory."""

        if not self.memory_manager:
            return 0.0

        try:
            past_attempts = self.memory_manager.retrieve(
                query=f"outcome related to {option.description}",
                memory_type=MemoryTier.EPISODIC,
                limit=5,
            )
        except Exception as error:  # noqa: BLE001 - defensive against external dependency
            logger.error("Error retrieving past outcomes: %s", error)
            return 0.0

        if not past_attempts:
            return 0.0

        successes = 0
        total = 0
        for item in past_attempts:
            if isinstance(item, MemoryItem):
                metadata = getattr(item, "metadata", {}) or {}
                if metadata.get("outcome") == "success":
                    successes += 1
                total += 1

        if total == 0:
            return 0.0

        success_rate = successes / total
        adjustment = (success_rate - 0.5) * 0.2
        logger.debug(
            "Option '%s': success_rate=%.2f adjustment=%.2f (successes=%s total=%s)",
            option.description,
            success_rate,
            adjustment,
            successes,
            total,
        )
        return adjustment

    def _maybe_generate_subplan(
        self,
        best_option: DecisionOption,
        context: dict[str, Any],
    ) -> None:
        """Trigger planning for complex actions when a planner is available."""

        plan_request = self._derive_plan_request(best_option)
        if not plan_request:
            return

        if not self.planner:
            logger.warning("Planner not available to create sub-plan for complex action '%s'.", best_option.description)
            return

        logger.info("Generating sub-plan for '%s' using goal '%s'.", best_option.description, plan_request)
        sub_plan = self.planner.generate_plan(goal_description=plan_request, context=context)
        if sub_plan:
            best_option.action = sub_plan
            logger.info("Attached generated sub-plan to option '%s'.", best_option.description)
        else:
            logger.error("Failed to generate sub-plan for '%s'.", best_option.description)

    @staticmethod
    def _derive_plan_request(option: DecisionOption) -> Optional[str]:
        """Determine whether additional planning is required for an option."""

        action = option.action
        if isinstance(action, str) and action.startswith("goal:"):
            _, _, goal = action.partition(":")
            return goal.strip() or option.description

        if isinstance(action, dict) and action.get("type") == "complex_action":
            return option.description

        return None
