"""Smoke tests validating CLI and demo script entry points.

These tests ensure the Typer CLI and showcase scripts can be imported and run
basic flows without crashing. They intentionally focus on exercising the public
interfaces while keeping execution time short.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Dict, List

import pytest
from typer.testing import CliRunner

from neuroca.cli.main import app, state as cli_state
from scripts import basic_memory_test, test_memory_with_llm


@dataclass
class _StubMemory:
    """Minimal memory representation used by the stub manager."""

    id: str
    text: str

    def get_text(self) -> str:
        return self.text


@dataclass
class _StubMemorySearchResult:
    """Subset of ``MemorySearchResult`` features used by the scripts."""

    memory: _StubMemory
    relevance: float = 1.0
    tier: str = "stm"


@dataclass
class _StubMemorySearchResults:
    """Container mirroring the ``MemorySearchResults`` interface."""

    results: List[_StubMemorySearchResult]
    total_count: int
    query: str
    options: SimpleNamespace
    execution_time_ms: float = 0.0


class _StubMemoryManager:
    """Lightweight async stand-in for ``MemoryManager`` used in smoke tests."""

    def __init__(self, *args, **kwargs) -> None:  # pragma: no cover - trivial plumbing
        self._counter = 0
        self._memories: Dict[str, _StubMemory] = {}

    async def initialize(self) -> None:
        return None

    async def add_memory(
        self,
        *,
        content,
        summary=None,
        importance=0.5,
        metadata=None,
        tags=None,
        initial_tier="stm",
        **_: object,
    ) -> str:
        self._counter += 1
        memory_id = f"mem-{self._counter}"
        text = content if isinstance(content, str) else str(content)
        self._memories[memory_id] = _StubMemory(id=memory_id, text=text)
        return memory_id

    async def retrieve_memory(self, memory_id: str):  # pragma: no cover - exercised via smoke tests
        return self._memories.get(memory_id)

    async def search_memories(
        self,
        *,
        query: str | None = None,
        limit: int = 5,
        tiers: List[str] | None = None,
        **_: object,
    ) -> _StubMemorySearchResults:
        tier = tiers[0] if tiers else "stm"
        ordered = list(self._memories.values())[:limit]
        results = [_StubMemorySearchResult(memory=m, tier=tier) for m in ordered]
        return _StubMemorySearchResults(
            results=results,
            total_count=len(self._memories),
            query=query or "",
            options=SimpleNamespace(limit=limit, tiers=tiers),
        )

    async def shutdown(self) -> None:
        return None


def test_cli_version_command_runs_successfully(monkeypatch: pytest.MonkeyPatch) -> None:
    """The Typer CLI should execute the ``version`` command without errors."""

    monkeypatch.setitem(cli_state, "config_manager", None)
    runner = CliRunner()
    result = runner.invoke(app, ["version"])

    assert result.exit_code == 0
    assert "NeuroCognitive Architecture" in result.stdout


@pytest.mark.asyncio
async def test_basic_memory_script_main(monkeypatch: pytest.MonkeyPatch) -> None:
    """Execute ``basic_memory_test.main`` end-to-end with a fast sleep."""

    async def _fast_sleep(_: float) -> None:  # pragma: no cover - trivial helper
        return None

    monkeypatch.setattr(basic_memory_test, "MemoryManager", _StubMemoryManager)
    monkeypatch.setattr(basic_memory_test.asyncio, "sleep", _fast_sleep)

    await basic_memory_test.main()


@pytest.mark.asyncio
async def test_conversational_agent_smoke(monkeypatch: pytest.MonkeyPatch) -> None:
    """Initialize the conversational agent script and process a single message."""

    monkeypatch.setattr(test_memory_with_llm, "OPENAI_AVAILABLE", False, raising=False)
    monkeypatch.setattr(test_memory_with_llm, "MemoryManager", _StubMemoryManager)

    agent = test_memory_with_llm.ConversationalAgent()
    await agent.initialize()

    response = await agent.process_message("Hello, Neuroca!")
    assert isinstance(response, str)
    assert response

    await agent.shutdown()
