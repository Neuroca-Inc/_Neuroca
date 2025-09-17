"""Unit tests for the DecisionMaker component in cognitive control."""

from typing import Any
from unittest.mock import MagicMock

import pytest

from neuroca.core.cognitive_control.decision_maker import DecisionMaker, DecisionOption
from neuroca.core.health.dynamics import HealthState
from neuroca.memory.manager import MemoryItem, MemoryManager


def create_context(health_state: HealthState = HealthState.NORMAL, **kwargs: Any) -> dict[str, Any]:
    """Utility helper to build decision contexts for tests."""

    context = {"health_state": health_state}
    context.update(kwargs)
    return context


class TestDecisionMaker:
    """Tests for the DecisionMaker class."""

    @pytest.fixture()
    def mock_memory_manager(self) -> MagicMock:
        """Fixture for a mocked MemoryManager using the async API."""

        manager = MagicMock(spec=MemoryManager)
        manager.search_memories.return_value = []
        return manager

    @pytest.fixture()
    def decision_maker(self, mock_memory_manager: MagicMock) -> DecisionMaker:
        """Create a DecisionMaker wired to the mocked memory manager."""

        return DecisionMaker(memory_manager=mock_memory_manager)

    @pytest.fixture()
    def sample_options(self) -> list[DecisionOption]:
        """Provide reusable decision options for scoring tests."""

        return [
            DecisionOption(description="Option A (Low Risk, Med Utility)", action="action_a", estimated_utility=0.6, risk=0.1),
            DecisionOption(description="Option B (High Risk, High Utility)", action="action_b", estimated_utility=0.9, risk=0.7),
            DecisionOption(description="Option C (Med Risk, Low Utility)", action="action_c", estimated_utility=0.3, risk=0.4),
        ]

    @pytest.mark.asyncio
    async def test_initialization(self, decision_maker: DecisionMaker, mock_memory_manager: MagicMock) -> None:
        """The decision maker should retain provided collaborators."""

        assert decision_maker.memory_manager is mock_memory_manager
        assert decision_maker.health_manager is None
        assert decision_maker.planner is None
        assert decision_maker.goal_manager is None

    @pytest.mark.asyncio
    async def test_choose_action_no_options(self, decision_maker: DecisionMaker) -> None:
        """Choosing with no options should return ``None``."""

        choice = await decision_maker.choose_action([], context=create_context())
        assert choice is None

    @pytest.mark.asyncio
    async def test_choose_action_normal_health(
        self,
        decision_maker: DecisionMaker,
        sample_options: list[DecisionOption],
    ) -> None:
        """In a normal health state, either balanced option may be selected."""

        context = create_context(HealthState.NORMAL)
        choice = await decision_maker.choose_action(sample_options, context)

        assert choice is not None
        assert choice.description in {
            "Option A (Low Risk, Med Utility)",
            "Option B (High Risk, High Utility)",
        }

    @pytest.mark.asyncio
    async def test_choose_action_stressed_health(
        self,
        decision_maker: DecisionMaker,
        sample_options: list[DecisionOption],
    ) -> None:
        """Stressed health increases risk aversion favoring safer options."""

        context = create_context(HealthState.STRESSED)
        choice = await decision_maker.choose_action(sample_options, context)

        assert choice is not None
        assert choice.description == "Option A (Low Risk, Med Utility)"

    @pytest.mark.asyncio
    async def test_choose_action_critical_health(
        self,
        decision_maker: DecisionMaker,
        sample_options: list[DecisionOption],
    ) -> None:
        """Critical health should always select the safest option."""

        context = create_context(HealthState.CRITICAL)
        choice = await decision_maker.choose_action(sample_options, context)

        assert choice is not None
        assert choice.description == "Option A (Low Risk, Med Utility)"

    @pytest.mark.asyncio
    async def test_choose_action_optimal_health(
        self,
        decision_maker: DecisionMaker,
        sample_options: list[DecisionOption],
    ) -> None:
        """Optimal health reduces risk aversion, rewarding ambitious options."""

        context = create_context(HealthState.OPTIMAL)
        choice = await decision_maker.choose_action(sample_options, context)

        assert choice is not None
        assert choice.description == "Option B (High Risk, High Utility)"

    @pytest.mark.asyncio
    async def test_choose_action_with_goal_bonus(self, decision_maker: DecisionMaker) -> None:
        """Goal-aligned options should benefit from the bonus score."""

        options = [
            DecisionOption(description="Aligns with default_goal", action="action_a", estimated_utility=0.5, risk=0.1),
            DecisionOption(description="Does not align", action="action_b", estimated_utility=0.6, risk=0.1),
        ]
        context = create_context(HealthState.NORMAL)
        choice = await decision_maker.choose_action(options, context)

        assert choice is not None
        assert choice.description == "Aligns with default_goal"

    @pytest.mark.asyncio
    async def test_choose_action_past_success(
        self,
        decision_maker: DecisionMaker,
        mock_memory_manager: MagicMock,
    ) -> None:
        """Positive episodic results should raise an option's utility."""

        options = [
            DecisionOption(description="Option Good History", action="action_a", estimated_utility=0.5, risk=0.1),
            DecisionOption(description="Option Neutral History", action="action_b", estimated_utility=0.5, risk=0.1),
        ]
        success_item = MagicMock(spec=MemoryItem)
        success_item.metadata = {"outcome": "success"}

        async def success_side_effect(*, query: str, **_: Any) -> list[MemoryItem]:
            if "Good History" in query:
                return [success_item] * 3
            return []

        mock_memory_manager.search_memories.side_effect = success_side_effect

        context = create_context(HealthState.NORMAL)
        choice = await decision_maker.choose_action(options, context)

        assert choice is not None
        assert choice.description == "Option Good History"

    @pytest.mark.asyncio
    async def test_choose_action_past_failure(
        self,
        decision_maker: DecisionMaker,
        mock_memory_manager: MagicMock,
    ) -> None:
        """Negative episodic results should lower an option's appeal."""

        options = [
            DecisionOption(description="Option Bad History", action="action_a", estimated_utility=0.5, risk=0.1),
            DecisionOption(description="Option Neutral History", action="action_b", estimated_utility=0.5, risk=0.1),
        ]
        failure_item = MagicMock(spec=MemoryItem)
        failure_item.metadata = {"outcome": "failure"}

        async def failure_side_effect(*, query: str, **_: Any) -> list[MemoryItem]:
            if "Bad History" in query:
                return [failure_item] * 3
            return []

        mock_memory_manager.search_memories.side_effect = failure_side_effect

        context = create_context(HealthState.NORMAL)
        options[1].estimated_utility = 0.51
        choice = await decision_maker.choose_action(options, context)

        assert choice is not None
        assert choice.description == "Option Neutral History"


class TestDecisionOption:
    """Tests for the DecisionOption class."""

    def test_decision_option_init(self):
        option = DecisionOption(description="Test Option", action="do_test", estimated_utility=0.8, risk=0.2)
        assert option.description == "Test Option"
        assert option.action == "do_test"
        assert option.estimated_utility == 0.8
        assert option.risk == 0.2
