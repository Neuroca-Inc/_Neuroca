"""Tests for memory prompt helpers."""

from neuroca.integration.prompts import memory


def test_memory_consolidation_prompt_builds_messages():
    memory_items = [
        {
            "id": "item-1",
            "content": "A short fact",
            "timestamp": 1700000000,
        }
    ]

    prompt = memory.get_memory_consolidation_prompt(
        memory_items=memory_items,
        source_memory_type="working",
        target_memory_type="episodic",
        consolidation_criteria="high relevance",
    )

    assert prompt["messages"][0]["role"] == "system"
    assert "Memory Consolidation Process" in prompt["messages"][1]["content"]


def test_memory_forgetting_prompt_accepts_items():
    items = [
        {
            "id": "mem-1",
            "content": "Outdated detail",
            "timestamp": 1700000500,
        }
    ]

    prompt = memory.get_memory_forgetting_prompt(
        memory_items=items,
        memory_type="episodic",
        forgetting_criteria="older than a week",
        retention_importance="maintain mission critical items",
    )

    assert prompt["messages"][1]["content"].count("Memory Items to Evaluate") == 1


def test_memory_search_prompt_formats_parameters():
    prompt = memory.get_memory_search_prompt(
        query="recent updates",
        memory_types=["working", "semantic"],
        search_parameters={"limit": 5, "filters": {"tag": "ops"}},
    )

    user_content = prompt["messages"][1]["content"]
    assert "Memory Types to Search" in user_content
    assert "limit" in user_content


def test_format_memory_for_prompt_limits_fields():
    formatted = memory.format_memory_for_prompt(
        memories=[
            {
                "id": "1",
                "content": "Example",
                "metadata": {"source": "system"},
            }
        ],
        include_fields=["id", "content"],
    )

    assert "Memory 1:" in formatted
    assert "metadata" not in formatted
