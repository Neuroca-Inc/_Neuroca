"""Asynchronous planning routines for the cognitive-control system."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional, Sequence

from neuroca.core.enums import MemoryTier
from neuroca.core.health.dynamics import HealthState

from ._async_utils import extract_content, search_memories

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class PlanStep:
    """Represents a single step within a larger plan."""

    action: str
    parameters: dict[str, Any] = field(default_factory=dict)
    estimated_cost: float = 0.1
    status: str = "pending"


@dataclass
class Plan:
    """Represents a sequence of actions to achieve a goal."""

    goal: str
    steps: list[PlanStep]
    current_step_index: int = 0
    status: str = "pending"

    def get_next_step(self) -> Optional[PlanStep]:
        if self.status not in {"pending", "executing"}:
            return None
        if self.current_step_index >= len(self.steps):
            self.status = "completed"
            return None
        step = self.steps[self.current_step_index]
        step.status = "executing"
        self.status = "executing"
        return step

    def update_step_status(self, step_index: int, status: str, message: Optional[str] = None) -> None:
        if not (0 <= step_index < len(self.steps)):
            logger.warning("Attempted to update invalid step index %s for plan '%s'", step_index, self.goal)
            return

        step = self.steps[step_index]
        step.status = status
        logger.info(
            "Plan '%s': Step %s ('%s') status updated to %s. %s",
            self.goal,
            step_index,
            step.action,
            status,
            message or "",
        )

        if status == "completed":
            self.current_step_index += 1
            if self.current_step_index >= len(self.steps):
                self.status = "completed"
                logger.info("Plan '%s' completed successfully.", self.goal)
        elif status == "failed":
            self.status = "failed"
            logger.error("Plan '%s' failed at step %s: %s", self.goal, step_index, message or "Unknown reason")


class Planner:
    """Generates and manages plans for achieving goals."""

    def __init__(
        self,
        memory_manager: Any | None = None,
        health_manager: Any | None = None,
        goal_manager: Any | None = None,
    ) -> None:
        logger.info("Planner initialized.")
        self.memory_manager = memory_manager
        self.health_manager = health_manager
        self.goal_manager = goal_manager

    async def generate_plan(
        self,
        goal_description: str,
        context: Optional[dict[str, Any]] = None,
    ) -> Optional[Plan]:
        """Generate a plan to achieve the specified goal description."""
        logger.info("Generating plan for goal: %s", goal_description)
        context = dict(context or {})

        health_state = context.get("health_state", HealthState.NORMAL)
        if not isinstance(health_state, HealthState):
            try:
                normalized = str(health_state).split(".")[-1].upper()
                health_state = HealthState[normalized]
            except Exception:  # noqa: BLE001
                health_state = HealthState.NORMAL

        if health_state in {HealthState.IMPAIRED, HealthState.CRITICAL}:
            logger.warning(
                "Cannot generate complex plan in %s state. Aborting planning for '%s'.",
                health_state.value,
                goal_description,
            )
            return None

        semantic_knowledge: list[Any] = []
        episodic_knowledge: list[Any] = []
        if self.memory_manager:
            try:
                semantic_knowledge = await search_memories(
                    self.memory_manager,
                    query=f"procedure for {goal_description}",
                    limit=1,
                    tiers=[MemoryTier.SEMANTIC],
                )
                episodic_knowledge = await search_memories(
                    self.memory_manager,
                    query=f"past plan {goal_description}",
                    limit=3,
                    tiers=[MemoryTier.EPISODIC],
                )
                logger.debug(
                    "Retrieved %s semantic and %s episodic memories for planning.",
                    len(semantic_knowledge),
                    len(episodic_knowledge),
                )
            except Exception:  # noqa: BLE001
                logger.exception("Error retrieving knowledge during planning")

        plan: Plan | None = None

        if semantic_knowledge:
            knowledge_item = semantic_knowledge[0]
            content = extract_content(knowledge_item)
            if isinstance(content, dict) and content.get("type") == "procedure":
                steps_data = content.get("steps")
                if isinstance(steps_data, Sequence) and steps_data:
                    steps: list[PlanStep] = []
                    for index, step_info in enumerate(steps_data):
                        if isinstance(step_info, dict) and "action" in step_info:
                            steps.append(
                                PlanStep(
                                    action=str(step_info["action"]),
                                    parameters=dict(step_info.get("parameters", {})),
                                    estimated_cost=float(step_info.get("cost", 0.1)),
                                )
                            )
                        else:
                            logger.warning(
                                "Invalid step format in known procedure (step %s): %s",
                                index,
                                step_info,
                            )
                            steps = []
                            break

                    if steps:
                        plan = Plan(goal=goal_description, steps=steps)
                        logger.info(
                            "Successfully constructed plan with %s steps from semantic knowledge.",
                            len(steps),
                        )
                else:
                    logger.warning("Known procedure found but contained no valid steps.")
            else:
                logger.warning("Retrieved semantic knowledge was not a valid procedure dictionary.")

        if not plan and episodic_knowledge:
            logger.info(
                "Found %s related past episodes. Adaptation logic not implemented.",
                len(episodic_knowledge),
            )

        if not plan:
            logger.debug(
                "No knowledge-based plan found for '%s'. Attempting generic decomposition.",
                goal_description,
            )
            steps = self._generic_decomposition(goal_description, context, health_state)
            if steps:
                plan = Plan(goal=goal_description, steps=steps)
            else:
                logger.error("Failed to generate any steps for goal: %s", goal_description)

        if plan:
            logger.info(
                "Generated plan with %s steps for goal: %s (Health State: %s)",
                len(plan.steps),
                goal_description,
                health_state.value,
            )
        else:
            logger.warning("No planning strategy found for goal: %s", goal_description)

        return plan

    def _generic_decomposition(
        self,
        goal_description: str,
        context: dict[str, Any],
        health_state: HealthState,
    ) -> list[PlanStep]:
        steps: list[PlanStep] = []
        words = goal_description.lower().split()
        if words:
            action_verb = words[0]
            action_object = " ".join(words[1:]) if len(words) > 1 else "default_target"
            steps.extend(
                [
                    PlanStep(action=f"prepare_{action_verb}", parameters={"target": action_object}, estimated_cost=0.2),
                    PlanStep(action=f"execute_{action_verb}", parameters={"target": action_object}, estimated_cost=0.6),
                    PlanStep(action=f"verify_{action_verb}", parameters={"target": action_object}, estimated_cost=0.2),
                ]
            )
            logger.info(
                "Created generic 3-step plan based on goal words: %s, %s",
                action_verb,
                action_object,
            )
        else:
            logger.warning("Cannot decompose empty goal description.")

        if len(steps) <= 1:
            rule_based_steps: list[PlanStep] = []
            goal_lower = goal_description.lower()
            if "make" in goal_lower and "tea" in goal_lower:
                if health_state == HealthState.FATIGUED:
                    logger.info("Applying simplified 'make tea' rule due to FATIGUED state.")
                    rule_based_steps = [
                        PlanStep(action="boil_water", estimated_cost=0.4),
                        PlanStep(action="make_tea_simple", estimated_cost=0.2),
                    ]
                else:
                    logger.info("Applying standard 'make tea' rule.")
                    rule_based_steps = [
                        PlanStep(action="find_kettle", estimated_cost=0.1),
                        PlanStep(action="fill_kettle", parameters={"water_level": "full"}, estimated_cost=0.1),
                        PlanStep(action="boil_water", estimated_cost=0.3),
                        PlanStep(action="find_mug_and_tea_bag", estimated_cost=0.1),
                        PlanStep(action="pour_water", estimated_cost=0.1),
                        PlanStep(action="steep_tea", parameters={"duration_seconds": 180}, estimated_cost=0.05),
                    ]
            elif "resolve" in goal_lower and ("dependency" in goal_lower or "conflict" in goal_lower):
                logger.info("Applying 'resolve dependency/conflict' rule.")
                target = context.get("target_entity", "unknown")
                rule_based_steps = [
                    PlanStep(action="analyze_situation", parameters={"target": target}, estimated_cost=0.5),
                    PlanStep(action="identify_root_cause", estimated_cost=0.4),
                    PlanStep(action="generate_solutions", estimated_cost=0.3),
                    PlanStep(action="select_best_solution", estimated_cost=0.1),
                    PlanStep(action="implement_solution", estimated_cost=0.4),
                    PlanStep(action="verify_resolution", estimated_cost=0.2),
                ]

            if rule_based_steps:
                logger.info("Replacing generic plan with rule-based plan.")
                steps = rule_based_steps

        return steps

    async def replan(
        self,
        failed_plan: Plan,
        reason: str,
        context: Optional[dict[str, Any]] = None,
    ) -> Optional[Plan]:
        """Generate a new plan after a previous plan failed."""
        logger.warning("Replanning required for goal '%s' due to failure: %s", failed_plan.goal, reason)

        if "resource" in reason.lower() or "energy" in reason.lower():
            logger.info("Replanning: Attempting less costly alternative due to resource failure.")
            modified_context = dict(context or {})
            modified_context["planning_constraint"] = "low_resource"
            new_plan = await self.generate_plan(failed_plan.goal, modified_context)
            if new_plan:
                return new_plan

        failed_step_index = failed_plan.current_step_index
        if 0 <= failed_step_index < len(failed_plan.steps):
            failed_action = failed_plan.steps[failed_step_index].action
            if failed_action == "find_kettle":
                logger.info("Replanning: Kettle not found, trying alternative 'use_microwave'.")
                new_steps = failed_plan.steps[:failed_step_index]
                new_steps.append(PlanStep(action="use_microwave", estimated_cost=0.2))
                new_steps.extend(failed_plan.steps[failed_step_index + 1 :])
                if new_steps:
                    return Plan(goal=failed_plan.goal, steps=new_steps)

        logger.info("Replanning: Defaulting to generating plan from scratch.")
        return await self.generate_plan(failed_plan.goal, context)
