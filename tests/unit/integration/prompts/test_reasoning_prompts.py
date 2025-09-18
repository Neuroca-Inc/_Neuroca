"""Tests for reasoning prompt templates."""

from neuroca.integration.prompts.reasoning import (
    ChainOfThoughtPrompt,
    ReasoningExample,
)


def test_reasoning_example_validates_fields():
    example = ReasoningExample(
        problem="What is 2 + 2?",
        reasoning="Add the numbers together",
        answer="4",
    )

    prompt = ChainOfThoughtPrompt(
        task_description="Solve arithmetic",
        examples=[example],
    )

    formatted = prompt.format(problem="What is 3 + 5?")

    assert "Chain-of-thought" not in formatted.lower()
    assert "Problem: What is 3 + 5?" in formatted
