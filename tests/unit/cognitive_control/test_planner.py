"""Unit tests for the Planner component in cognitive control."""

from typing import Any
from unittest.mock import MagicMock

import pytest

from neuroca.core.cognitive_control.planner import Plan, Planner, PlanStep
from neuroca.core.health.dynamics import HealthState
from neuroca.memory.manager import MemoryItem, MemoryManager


def create_context(health_state: HealthState = HealthState.NORMAL, **kwargs: Any) -> dict[str, Any]:
    """Helper to build planner contexts with an optional health override."""

    context = {"health_state": health_state}
    context.update(kwargs)
    return context


class TestPlanner:
    """Tests for the asynchronous Planner class."""

    @pytest.fixture()
    def mock_memory_manager(self) -> MagicMock:
        """Provide a mocked memory manager exposing async search semantics."""

        manager = MagicMock(spec=MemoryManager)
        manager.search_memories.return_value = []
        return manager

    @pytest.fixture()
    def planner(self, mock_memory_manager: MagicMock) -> Planner:
        """Create a planner bound to the mocked collaborators."""

        return Planner(memory_manager=mock_memory_manager, health_manager=None, goal_manager=None)

    @pytest.mark.asyncio
    async def test_initialization(self, planner: Planner, mock_memory_manager: MagicMock) -> None:
        """Planner should retain provided dependencies."""

        assert planner.memory_manager is mock_memory_manager
        assert planner.health_manager is None
        assert planner.goal_manager is None

    @pytest.mark.asyncio
    async def test_generate_plan_make_tea_normal_health(self, planner: Planner) -> None:
        """Generating a plan with no knowledge falls back to the generic blueprint."""

        context = create_context(HealthState.NORMAL)
        plan = await planner.generate_plan("make tea", context)
        assert plan is not None
        assert isinstance(plan, Plan)
        assert plan.goal == "make tea"
        assert [step.action for step in plan.steps] == ["prepare_make", "execute_make", "verify_make"]

    @pytest.mark.asyncio
    async def test_generate_plan_make_tea_fatigued_health(self, planner: Planner) -> None:
        """Fatigued health still produces the default plan skeleton."""

        context = create_context(HealthState.FATIGUED)
        plan = await planner.generate_plan("make tea", context)
        assert plan is not None
        assert isinstance(plan, Plan)
        assert plan.goal == "make tea"
        assert [step.action for step in plan.steps] == ["prepare_make", "execute_make", "verify_make"]

    @pytest.mark.asyncio
    async def test_generate_plan_impaired_health(self, planner: Planner) -> None:
        """Impaired health prevents planning altogether."""

        context = create_context(HealthState.IMPAIRED)
        plan = await planner.generate_plan("make tea", context)
        assert plan is None

    @pytest.mark.asyncio
    async def test_generate_plan_critical_health(self, planner: Planner) -> None:
        """Critical health also aborts planning."""

        context = create_context(HealthState.CRITICAL)
        plan = await planner.generate_plan("make tea", context)
        assert plan is None

    @pytest.mark.asyncio
    async def test_generate_plan_resolve_dependency(self, planner: Planner) -> None:
        """Generic decomposition should respect contextual hints."""

        context = create_context(dependency_target="module_A")
        plan = await planner.generate_plan("resolve dependency conflict", context)
        assert plan is not None
        assert isinstance(plan, Plan)
        assert plan.goal == "resolve dependency conflict"
        assert plan.steps[0].action == "prepare_resolve"
        assert plan.steps[0].parameters.get("target") == "dependency conflict"
        assert plan.steps[-1].action == "verify_resolve"

    @pytest.mark.asyncio
    async def test_generate_plan_unknown_goal_generic_plan(self, planner: Planner) -> None:
        """Unknown goals default to a generic three-step outline."""

        context = create_context()
        plan = await planner.generate_plan("unknown complex goal", context)
        assert plan is not None
        assert isinstance(plan, Plan)
        assert plan.goal == "unknown complex goal"
        assert [step.action for step in plan.steps] == ["prepare_unknown", "execute_unknown", "verify_unknown"]
        assert plan.steps[0].parameters.get("target") == "complex goal"

    @pytest.mark.asyncio
    async def test_generate_plan_empty_goal(self, planner: Planner) -> None:
        """Empty goals should not yield plans."""

        context = create_context()
        plan = await planner.generate_plan("", context)
        assert plan is None

    @pytest.mark.asyncio
    async def test_replan_simple_retry(self, planner: Planner) -> None:
        """Replanning a failed goal regenerates a fresh pending plan."""

        context = create_context()
        original_plan = await planner.generate_plan("make tea", context)
        assert original_plan is not None
        original_plan.status = "failed"

        new_plan = await planner.replan(original_plan, "Kettle not found", context)
        assert new_plan is not None
        assert new_plan.goal == original_plan.goal
        assert new_plan.status == "pending"
        assert [step.action for step in new_plan.steps] == [step.action for step in original_plan.steps]

    @pytest.mark.asyncio
    async def test_replan_resource_failure(self, planner: Planner) -> None:
        """Resource failures fall back to regenerating an appropriate plan."""

        context = create_context()
        original_plan = await planner.generate_plan("make tea", context)
        assert original_plan is not None
        original_plan.status = "failed"

        await planner.replan(original_plan, "energy resource low", context)

        fatigued_context = create_context(HealthState.FATIGUED)
        fatigued_plan = await planner.generate_plan("make tea", fatigued_context)
        fatigued_plan.status = "failed"
        new_fatigued_plan = await planner.replan(fatigued_plan, "energy resource low", fatigued_context)

        assert new_fatigued_plan is not None
        assert [step.action for step in new_fatigued_plan.steps] == ["prepare_make", "execute_make", "verify_make"]

    @pytest.mark.asyncio
    async def test_replan_alternative_action(self, planner: Planner) -> None:
        """Alternative action replans still regenerate a coherent plan outline."""

        context = create_context()
        original_plan = await planner.generate_plan("make tea", context)
        assert original_plan is not None

        original_plan.current_step_index = 0
        original_plan.status = "failed"

        new_plan = await planner.replan(original_plan, "Kettle not found", context)

        assert new_plan is not None
        assert new_plan.goal == original_plan.goal
        assert [step.action for step in new_plan.steps] == ["prepare_make", "execute_make", "verify_make"]

    @pytest.mark.asyncio
    async def test_generate_plan_with_semantic_knowledge(
        self,
        planner: Planner,
        mock_memory_manager: MagicMock,
    ) -> None:
        """Semantic procedures should override the generic plan."""

        procedure_content = {
            "type": "procedure",
            "steps": [
                {"action": "semantic_step_1", "cost": 0.2},
                {"action": "semantic_step_2", "parameters": {"p": "v"}, "cost": 0.3},
            ],
        }
        mock_item = MagicMock(spec=MemoryItem)
        mock_item.content = procedure_content
        mock_item.id = "proc_123"

        async def search_side_effect(*, query: str, **_: Any) -> list[MemoryItem]:
            if "procedure" in query:
                return [mock_item]
            return []

        mock_memory_manager.search_memories.side_effect = search_side_effect

        context = create_context()
        plan = await planner.generate_plan("use known procedure", context)

        mock_memory_manager.search_memories.assert_awaited()
        assert plan is not None
        assert plan.goal == "use known procedure"
        assert [step.action for step in plan.steps] == ["semantic_step_1", "semantic_step_2"]
        assert plan.steps[1].parameters == {"p": "v"}
        assert plan.steps[0].estimated_cost == 0.2


class TestPlan:
    """Tests for the Plan and PlanStep classes."""

    def test_plan_step_init(self):
        step = PlanStep(action="test_action", parameters={"p1": 1}, estimated_cost=0.5)
        assert step.action == "test_action"
        assert step.parameters == {"p1": 1}
        assert step.estimated_cost == 0.5
        assert step.status == "pending"

    def test_plan_init(self):
        steps = [PlanStep("step1"), PlanStep("step2")]
        plan = Plan(goal="test_goal", steps=steps)
        assert plan.goal == "test_goal"
        assert plan.steps == steps
        assert plan.current_step_index == 0
        assert plan.status == "pending"

    def test_get_next_step(self):
        steps = [PlanStep("step1"), PlanStep("step2")]
        plan = Plan(goal="test_goal", steps=steps)
        
        step1 = plan.get_next_step()
        assert step1 is not None
        assert step1.action == "step1"
        assert step1.status == "executing"
        assert plan.status == "executing"
        assert plan.current_step_index == 0 # Index not incremented until status update

        # Mark step1 as completed
        plan.update_step_status(0, "completed")
        assert plan.current_step_index == 1

        step2 = plan.get_next_step()
        assert step2 is not None
        assert step2.action == "step2"
        assert step2.status == "executing"
        assert plan.status == "executing"
        assert plan.current_step_index == 1

        # Mark step2 as completed
        plan.update_step_status(1, "completed")
        assert plan.current_step_index == 2
        assert plan.status == "completed" # Plan completes

        step3 = plan.get_next_step()
        assert step3 is None # No more steps

    def test_get_next_step_already_completed(self):
        steps = [PlanStep("step1")]
        plan = Plan(goal="test_goal", steps=steps)
        plan.status = "completed"
        step = plan.get_next_step()
        assert step is None

    def test_update_step_status_completed(self):
        steps = [PlanStep("step1"), PlanStep("step2")]
        plan = Plan(goal="test_goal", steps=steps)
        plan.get_next_step() # Start step 0
        plan.update_step_status(0, "completed")
        assert plan.steps[0].status == "completed"
        assert plan.current_step_index == 1
        assert plan.status == "executing" # Plan still executing

        plan.get_next_step() # Start step 1
        plan.update_step_status(1, "completed")
        assert plan.steps[1].status == "completed"
        assert plan.current_step_index == 2
        assert plan.status == "completed" # Plan now completed

    def test_update_step_status_failed(self):
        steps = [PlanStep("step1"), PlanStep("step2")]
        plan = Plan(goal="test_goal", steps=steps)
        plan.get_next_step() # Start step 0
        plan.update_step_status(0, "failed", message="Resource unavailable")
        assert plan.steps[0].status == "failed"
        assert plan.status == "failed"
        assert plan.current_step_index == 0 # Index doesn't advance on failure

        # Cannot get next step if plan failed
        next_step = plan.get_next_step()
        assert next_step is None

    def test_update_step_status_invalid_index(self):
        steps = [PlanStep("step1")]
        plan = Plan(goal="test_goal", steps=steps)
        # Should log warning but not raise error
        plan.update_step_status(5, "completed") 
        assert plan.status == "pending" # Status unchanged
