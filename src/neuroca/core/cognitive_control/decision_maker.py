"""Asynchronous decision-making component for the NCA cognitive-control stack."""

from __future__ import annotations

import inspect
import logging
from dataclasses import dataclass
from typing import Any, Optional, Sequence

from neuroca.core.enums import MemoryTier
from neuroca.core.health.dynamics import HealthState

from ._async_utils import extract_metadata, search_memories

logger = logging.getLogger(__name__)

GOAL_ALIGNMENT_BONUS = 0.2


async def maybe_await_callable(func: Any, *args: Any, **kwargs: Any) -> Any:
    """Await functions that may be synchronous or asynchronous."""

    if inspect.iscoroutinefunction(func):
        return await func(*args, **kwargs)

    result = func(*args, **kwargs)
    if inspect.isawaitable(result):
        return await result
    return result


@dataclass(slots=True)
class DecisionOption:
    """Represents a potential choice or action to be evaluated."""

    description: str
    action: Any
    estimated_utility: float = 0.0
    risk: float = 0.0


class DecisionMaker:
    """Evaluate options and select actions based on goals and context."""

    def __init__(
        self,
        memory_manager: Any | None = None,
        health_manager: Any | None = None,
        planner: Any | None = None,
        goal_manager: Any | None = None,
    ) -> None:
        logger.info("DecisionMaker initialized.")
        self.memory_manager = memory_manager
        self.health_manager = health_manager
        self.planner = planner
        self.goal_manager = goal_manager

    async def choose_action(
        self,
        options: Sequence[DecisionOption],
        context: Optional[dict[str, Any]] = None,
    ) -> Optional[DecisionOption]:
        """Select the best action from a list of options using async memory hooks."""
        if not options:
            logger.warning("No options provided for decision making.")
            return None

        context = dict(context or {})

        current_goal_description = context.get("current_goal_description")
        if not current_goal_description and self.goal_manager:
            getter = getattr(self.goal_manager, "get_highest_priority_active_goal", None)
            if callable(getter):  # pragma: no cover - defensive branch
                try:
                    highest_goal = getter()
                except Exception:  # noqa: BLE001
                    logger.debug("Goal manager lookup failed", exc_info=True)
                else:
                    if highest_goal is not None:
                        current_goal_description = getattr(highest_goal, "description", None)

        if not current_goal_description:
            current_goal_description = "default_goal"

        health_state = context.get("health_state", HealthState.NORMAL)
        if not isinstance(health_state, HealthState):
            try:
                normalized = str(health_state).split(".")[-1].upper()
                health_state = HealthState[normalized]
            except Exception:  # noqa: BLE001
                health_state = HealthState.NORMAL

        risk_aversion_factor = self._determine_risk_aversion(health_state)

        best_option: DecisionOption | None = None
        max_adjusted_utility = float("-inf")

        for option in options:
            past_outcome_adjustment = await self._evaluate_past_outcomes(option)
            goal_alignment_bonus = (
                GOAL_ALIGNMENT_BONUS
                if self._is_goal_aligned(current_goal_description, option.description)
                else 0.0
            )
            adjusted_utility = (
                option.estimated_utility
                + goal_alignment_bonus
                + past_outcome_adjustment
                - (risk_aversion_factor * option.risk)
            )

            logger.debug(
                "Option '%s': base=%0.2f goal=%0.2f past=%0.2f risk=%0.2f final=%0.2f",
                option.description,
                option.estimated_utility,
                goal_alignment_bonus,
                past_outcome_adjustment,
                option.risk,
                adjusted_utility,
            )

            if adjusted_utility > max_adjusted_utility:
                max_adjusted_utility = adjusted_utility
                best_option = option

        if not best_option:
            logger.warning("Could not select a suitable option.")
            return None

        logger.info(
            "Selected option '%s' with adjusted utility %0.2f",
            best_option.description,
            max_adjusted_utility,
        )

        requires_plan, goal_for_plan = self._option_requires_plan(best_option)
        if requires_plan and self.planner:
            logger.info("Chosen action '%s' requires further planning.", best_option.description)
            try:
                sub_plan = await maybe_await_callable(
                    self.planner.generate_plan,
                    goal_description=goal_for_plan,
                    context=context,
                )
            except Exception:  # noqa: BLE001
                logger.exception("Planner failed to generate sub-plan for '%s'", best_option.description)
            else:
                if sub_plan:
                    best_option.action = sub_plan
                else:
                    logger.error("No sub-plan generated for '%s'", best_option.description)
        elif requires_plan:
            logger.warning("Planner not available to create sub-plan for complex action '%s'.", best_option.description)

        return best_option

    async def _evaluate_past_outcomes(
        self,
        option: DecisionOption,
        limit: int = 5,
        min_samples: int = 3,
    ) -> float:
        if not self.memory_manager:
            return 0.0

        query = f"outcome related to {option.description}"
        try:
            past_attempts = await search_memories(
                self.memory_manager,
                query=query,
                limit=limit,
                tiers=[MemoryTier.EPISODIC],
            )
        except Exception:  # noqa: BLE001
            logger.debug("Failed to retrieve past outcomes for '%s'", option.description, exc_info=True)
            return 0.0

        if not past_attempts:
            return 0.0

        success_count = 0
        evaluated_attempts = 0
        for item in past_attempts:
            metadata = extract_metadata(item)
            outcome = metadata.get("outcome") or metadata.get("result")
            if outcome is None:
                continue
            evaluated_attempts += 1
            if isinstance(outcome, str) and outcome.lower() == "success":
                success_count += 1
            elif isinstance(outcome, bool) and outcome:
                success_count += 1

        if evaluated_attempts == 0:
            return 0.0

        if evaluated_attempts < min_samples:
            success_rate = (success_count + 1) / (evaluated_attempts + 2)
        else:
            success_rate = success_count / evaluated_attempts
        adjustment = (success_rate - 0.5) * 0.2
        logger.debug(
            "Option '%s': past success rate %0.2f, adjustment %0.2f",
            option.description,
            success_rate,
            adjustment,
        )
        return adjustment

    @staticmethod
    def _is_goal_aligned(goal: Optional[str], option_desc: Optional[str]) -> bool:
        if not goal or not option_desc:
            return False
        goal_tokens = {token for token in goal.lower().split() if token}
        if not goal_tokens:
            return False
        option_tokens = {token for token in option_desc.lower().split() if token}
        return goal_tokens.issubset(option_tokens)

    @staticmethod
    def _determine_risk_aversion(health_state: HealthState) -> float:
        if health_state == HealthState.STRESSED:
            return 0.8
        if health_state in (HealthState.IMPAIRED, HealthState.CRITICAL):
            return 1.0
        if health_state == HealthState.OPTIMAL:
            return 0.3
        return 0.5

    @staticmethod
    def _option_requires_plan(option: DecisionOption) -> tuple[bool, Optional[str]]:
        if isinstance(option.action, str) and option.action.startswith("goal:"):
            return True, option.action.split(":", 1)[1].strip()
        if isinstance(option.action, dict) and option.action.get("type") == "complex_action":
            return True, option.description
        return False, None
