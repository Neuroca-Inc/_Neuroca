"""
Task Planning Component for NeuroCognitive Architecture (NCA).

This module implements the planning capabilities within the executive functions.
It is responsible for generating sequences of actions (plans) to achieve
specified goals, considering the current state, available resources (including
memory and health), and potential obstacles.

Key functionalities:
- Goal decomposition into sub-goals and tasks.
- Action sequence generation.
- Plan adaptation based on execution feedback and changing conditions.
- Resource estimation for planned actions.
"""

import logging
from typing import Any, Optional

from neuroca.core.enums import MemoryTier
from neuroca.core.health.dynamics import HealthState  # Example for context checking

# Import necessary components for potential integration
from neuroca.memory.models.memory_item import MemoryItem

# Configure logger
logger = logging.getLogger(__name__)

class PlanStep:
    """Represents a single step within a larger plan."""
    def __init__(self, action: str, parameters: Optional[dict[str, Any]] = None, estimated_cost: float = 0.1):
        self.action = action
        self.parameters = parameters or {}
        self.estimated_cost = estimated_cost # e.g., estimated energy/time cost
        self.status = "pending" # pending, executing, completed, failed

class Plan:
    """Represents a sequence of actions to achieve a goal."""
    def __init__(self, goal: str, steps: list[PlanStep]):
        self.goal = goal
        self.steps = steps
        self.current_step_index = 0
        self.status = "pending" # pending, executing, completed, failed, aborted

    def get_next_step(self) -> Optional[PlanStep]:
        """Get the next step to execute."""
        if self.status not in ["pending", "executing"]:
            return None
        if self.current_step_index < len(self.steps):
            step = self.steps[self.current_step_index]
            step.status = "executing"
            self.status = "executing"
            return step
        else:
            self.status = "completed"
            return None

    def update_step_status(self, step_index: int, status: str, message: Optional[str] = None):
        """Update the status of a specific step."""
        if 0 <= step_index < len(self.steps):
            self.steps[step_index].status = status
            logger.info(f"Plan '{self.goal}': Step {step_index} ('{self.steps[step_index].action}') status updated to {status}. {message or ''}")
            if status == "completed":
                 self.current_step_index += 1
                 if self.current_step_index >= len(self.steps):
                     self.status = "completed"
                     logger.info(f"Plan '{self.goal}' completed successfully.")
            elif status == "failed":
                 self.status = "failed"
                 logger.error(f"Plan '{self.goal}' failed at step {step_index}: {message or 'Unknown reason'}")
        else:
             logger.warning(f"Attempted to update invalid step index {step_index} for plan '{self.goal}'")


class Planner:
    """
    Generates and manages plans for achieving goals.

    Integrates with memory, health, and other cognitive components to create
    realistic and adaptive plans.
    """
    def __init__(self, memory_manager=None, health_manager=None, goal_manager=None):
        """
        Initialize the Planner.

        Args:
            memory_manager: Instance of MemoryManager for memory access.
            health_manager: Instance of HealthDynamicsManager for health status.
            goal_manager: Instance of GoalManager for goal context.
        """
        logger.info("Planner initialized.")
        self.memory_manager = memory_manager
        self.health_manager = health_manager
        self.goal_manager = goal_manager
        # NOTE: Consider implementing a proper dependency injection framework
        # for managing manager instances instead of direct constructor passing.

    def generate_plan(
        self,
        goal_description: str,
        context: Optional[dict[str, Any]] = None,
    ) -> Optional[Plan]:
        """Generate a plan to achieve the specified goal description."""

        logger.info("Generating plan for goal: %s", goal_description)
        context = context or {}
        health_state = self._resolve_health_state(context)
        if self._planning_blocked(health_state, goal_description):
            return None

        semantic_knowledge, episodic_knowledge = self._retrieve_knowledge(goal_description)
        plan = self._plan_from_semantic(goal_description, semantic_knowledge)
        if not plan and episodic_knowledge:
            self._log_episode_reference(goal_description, episodic_knowledge)

        if plan:
            return plan

        steps = self._generic_decomposition(goal_description, context, health_state)
        if not steps:
            logger.warning("No planning strategy found for goal: %s", goal_description)
            return None

        final_plan = Plan(goal=goal_description, steps=steps)
        logger.info(
            "Generated plan with %s steps for goal '%s' (health=%s)",
            len(final_plan.steps),
            goal_description,
            getattr(health_state, "value", health_state),
        )
        return final_plan

    @staticmethod
    def _resolve_health_state(context: dict[str, Any]) -> HealthState:
        value = context.get("health_state", HealthState.NORMAL)
        return value if isinstance(value, HealthState) else HealthState.NORMAL

    def _planning_blocked(self, health_state: HealthState, goal_description: str) -> bool:
        if health_state in {HealthState.IMPAIRED, HealthState.CRITICAL}:
            logger.warning(
                "Cannot generate complex plan in %s state. Aborting planning for '%s'.",
                health_state.value,
                goal_description,
            )
            return True
        return False

    def _retrieve_knowledge(self, goal_description: str) -> tuple[list[MemoryItem], list[MemoryItem]]:
        if not self.memory_manager:
            logger.debug("MemoryManager not available for planning knowledge retrieval.")
            return [], []

        semantic: list[MemoryItem] = []
        episodic: list[MemoryItem] = []
        try:
            semantic = self.memory_manager.retrieve(
                query=f"procedure for {goal_description}",
                memory_type=MemoryTier.SEMANTIC,
                limit=1,
            ) or []
            episodic = self.memory_manager.retrieve(
                query=f"past plan {goal_description}",
                memory_type=MemoryTier.EPISODIC,
                limit=3,
            ) or []
            logger.debug(
                "Retrieved %s semantic and %s episodic memories for planning.",
                len(semantic),
                len(episodic),
            )
        except Exception as error:  # noqa: BLE001 - memory lookups may fail
            logger.error("Error retrieving knowledge during planning: %s", error)
        return semantic, episodic

    def _plan_from_semantic(
        self,
        goal_description: str,
        semantic_knowledge: list[MemoryItem],
    ) -> Optional[Plan]:
        if not semantic_knowledge:
            return None

        item = semantic_knowledge[0]
        content = getattr(item, "content", {})
        if not isinstance(content, dict) or content.get("type") != "procedure":
            logger.warning("Semantic memory item %s was not a valid procedure dictionary.", getattr(item, "id", "unknown"))
            return None

        steps: list[PlanStep] = []
        procedure_steps = content.get("steps", [])
        for index, step_info in enumerate(procedure_steps):
            if not isinstance(step_info, dict) or "action" not in step_info:
                logger.warning("Invalid step format in known procedure (step %s): %s", index, step_info)
                return None
            steps.append(
                PlanStep(
                    action=step_info["action"],
                    parameters=step_info.get("parameters", {}),
                    estimated_cost=step_info.get("cost", 0.1),
                )
            )

        if not steps:
            logger.warning("Known procedure for '%s' contained no valid steps.", goal_description)
            return None

        logger.info(
            "Constructed plan with %s steps from semantic knowledge (ID: %s).",
            len(steps),
            getattr(item, "id", "unknown"),
        )
        return Plan(goal=goal_description, steps=steps)

    @staticmethod
    def _log_episode_reference(goal_description: str, episodic_knowledge: list[MemoryItem]) -> None:
        logger.info(
            "Found %s related past episodes for goal '%s'. Adaptation logic not implemented.",
            len(episodic_knowledge),
            goal_description,
        )

    def _generic_decomposition(
        self,
        goal_description: str,
        context: dict[str, Any],
        health_state: HealthState,
    ) -> list[PlanStep]:
        base_steps = self._base_steps_from_goal(goal_description)
        if not base_steps:
            return []
        return self._apply_rule_based_adjustments(goal_description, base_steps, context, health_state)

    @staticmethod
    def _base_steps_from_goal(goal_description: str) -> list[PlanStep]:
        words = goal_description.lower().split()
        if not words:
            logger.warning("Cannot decompose empty goal description.")
            return []

        action_verb = words[0]
        action_object = " ".join(words[1:]) if len(words) > 1 else "default_target"
        logger.info(
            "Created generic 3-step plan based on goal words: %s, %s",
            action_verb,
            action_object,
        )
        return [
            PlanStep(action=f"prepare_{action_verb}", parameters={"target": action_object}, estimated_cost=0.2),
            PlanStep(action=f"execute_{action_verb}", parameters={"target": action_object}, estimated_cost=0.6),
            PlanStep(action=f"verify_{action_verb}", parameters={"target": action_object}, estimated_cost=0.2),
        ]

    def _apply_rule_based_adjustments(
        self,
        goal_description: str,
        steps: list[PlanStep],
        context: dict[str, Any],
        health_state: HealthState,
    ) -> list[PlanStep]:
        if len(steps) > 1:
            return steps

        lowered_goal = goal_description.lower()
        if "make" in lowered_goal and "tea" in lowered_goal:
            return self._make_tea_steps(health_state)
        if "resolve" in lowered_goal and ("dependency" in lowered_goal or "conflict" in lowered_goal):
            target = context.get("target_entity", "unknown")
            return self._resolve_dependency_steps(target)
        return steps

    @staticmethod
    def _make_tea_steps(health_state: HealthState) -> list[PlanStep]:
        if health_state == HealthState.FATIGUED:
            logger.info("Applying simplified 'make tea' rule due to FATIGUED state.")
            return [
                PlanStep(action="boil_water", estimated_cost=0.4),
                PlanStep(action="make_tea_simple", estimated_cost=0.2),
            ]

        logger.info("Applying standard 'make tea' rule.")
        return [
            PlanStep(action="find_kettle", estimated_cost=0.1),
            PlanStep(action="fill_kettle", parameters={"water_level": "full"}, estimated_cost=0.1),
            PlanStep(action="boil_water", estimated_cost=0.3),
            PlanStep(action="find_mug_and_tea_bag", estimated_cost=0.1),
            PlanStep(action="pour_water", estimated_cost=0.1),
            PlanStep(action="steep_tea", parameters={"duration_seconds": 180}, estimated_cost=0.05),
        ]

    @staticmethod
    def _resolve_dependency_steps(target: str) -> list[PlanStep]:
        logger.info("Applying 'resolve dependency/conflict' rule.")
        return [
            PlanStep(action="analyze_situation", parameters={"target": target}, estimated_cost=0.5),
            PlanStep(action="identify_root_cause", estimated_cost=0.4),
            PlanStep(action="generate_solutions", estimated_cost=0.3),
            PlanStep(action="select_best_solution", estimated_cost=0.1),
            PlanStep(action="implement_solution", estimated_cost=0.4),
            PlanStep(action="verify_resolution", estimated_cost=0.2),
        ]

    def replan(self, failed_plan: Plan, reason: str, context: Optional[dict[str, Any]] = None) -> Optional[Plan]:
        """
        Generate a new plan after a previous plan failed.

        Args:
            failed_plan: The plan that failed.
            reason: The reason for the failure.
            context: Current situational information.

        Returns:
            A new Plan object, or None if replanning fails.
        """
        logger.warning(f"Replanning required for goal '{failed_plan.goal}' due to failure: {reason}")
        # --- Placeholder Replanning Logic ---
        # 1. Analyze the failure reason and context.
        # 2. Identify the problematic step(s).
        # 3. Retrieve alternative strategies or knowledge from memory (placeholder).
        # alternatives = self.memory_manager.retrieve(query=f"alternative for {failed_plan.steps[failed_plan.current_step_index].action}")
        
        # 4. Generate a revised or completely new plan.
        
        # Example: If the failure was resource-related, maybe try a less costly alternative step?
        if "resource" in reason.lower() or "energy" in reason.lower():
             logger.info("Replanning: Attempting less costly alternative due to resource failure.")
             # Try generating a new plan, potentially with constraints or simpler steps
             # This might involve passing modified context to generate_plan
             modified_context = context.copy() if context else {}
             modified_context["planning_constraint"] = "low_resource"
             new_plan = self.generate_plan(failed_plan.goal, modified_context)
             if new_plan:
                 return new_plan
             # Fallback if no low-resource plan generated: skip the step? (Risky)

        # Example: If a specific action failed (e.g., 'find_kettle'), try an alternative action?
        failed_step_index = failed_plan.current_step_index
        if 0 <= failed_step_index < len(failed_plan.steps):
             failed_action = failed_plan.steps[failed_step_index].action
             if failed_action == "find_kettle":
                 logger.info("Replanning: Kettle not found, trying alternative 'use_microwave'.")
                 new_steps = failed_plan.steps[:failed_step_index] # Steps before failure
                 # Replace failed step and potentially subsequent steps
                 new_steps.append(PlanStep(action="use_microwave", estimated_cost=0.2)) 
                 # Need to adjust subsequent steps that depended on the kettle... complex!
                 # For placeholder, just replace and hope subsequent steps still make sense or fail later.
                 new_steps.extend(failed_plan.steps[failed_step_index+1:]) 
                 if new_steps:
                      return Plan(goal=failed_plan.goal, steps=new_steps)

        # Default fallback: Try generating the plan from scratch again (original simplistic retry)
        logger.info("Replanning: Defaulting to generating plan from scratch.")
        return self.generate_plan(failed_plan.goal, context) 
        # --- End Enhanced Placeholder ---
