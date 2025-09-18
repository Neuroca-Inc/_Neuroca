from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

import pytest
from typer.testing import CliRunner

from neuroca.cli.commands.memory import memory_app
from neuroca.memory.backends.vector.components.integrity import VectorIndexIntegrityReport


runner = CliRunner()


class StubVectorBackend:
    def __init__(self) -> None:
        self.reindex_calls: List[Dict[str, Any]] = []
        self.check_calls: List[Dict[str, Any]] = []

    async def reindex(
        self,
        target_ids: Optional[List[str]] = None,
        *,
        full_refresh: bool = False,
        drift_threshold: float = 0.1,
    ) -> VectorIndexIntegrityReport:
        self.reindex_calls.append(
            {
                "target_ids": target_ids,
                "full_refresh": full_refresh,
                "drift_threshold": drift_threshold,
            }
        )
        return VectorIndexIntegrityReport(
            index_entry_count=2,
            metadata_entry_count=2,
            checked_entry_count=2,
            reindexed=True,
            reindexed_entry_count=2,
        )

    async def check_index_integrity(
        self,
        *,
        drift_threshold: float = 0.1,
        sample_size: Optional[int] = None,
    ) -> VectorIndexIntegrityReport:
        self.check_calls.append(
            {
                "drift_threshold": drift_threshold,
                "sample_size": sample_size,
            }
        )
        return VectorIndexIntegrityReport(
            index_entry_count=1,
            metadata_entry_count=1,
            checked_entry_count=1,
        )


class StubMemoryManager:
    def __init__(self) -> None:
        self.add_calls: List[Dict[str, Any]] = []
        self.search_calls: List[Dict[str, Any]] = []
        self.consolidate_calls: List[Dict[str, Any]] = []
        self.vector_backend = StubVectorBackend()
        self._ltm = SimpleNamespace(_backend=self.vector_backend)
        self.initialized = False

    async def initialize(self) -> None:
        self.initialized = True

    async def shutdown(self) -> None:
        self.initialized = False

    async def add_memory(self, **payload: Any) -> str:
        self.add_calls.append(payload)
        return f"mem-{len(self.add_calls)}"

    async def search_memories(self, **params: Any) -> List[Dict[str, Any]]:
        self.search_calls.append(params)
        tier = params.get("tiers", ["stm"])
        return [
            {
                "id": "mem-1",
                "tier": tier[0] if isinstance(tier, list) and tier else tier,
                "content": {"text": "Alpha content", "summary": "Alpha summary"},
                "metadata": {"importance": 0.8, "tags": {"alpha": True}},
            }
        ]

    async def consolidate_memory(
        self,
        memory_id: str,
        *,
        source_tier: str,
        target_tier: str,
        additional_metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        self.consolidate_calls.append(
            {
                "memory_id": memory_id,
                "source_tier": source_tier,
                "target_tier": target_tier,
                "metadata": additional_metadata,
            }
        )
        return f"{memory_id}-consolidated"

    @property
    def ltm_storage(self) -> Any:
        return self._ltm


@pytest.fixture()
def stub_manager(monkeypatch: pytest.MonkeyPatch) -> StubMemoryManager:
    manager = StubMemoryManager()

    def _factory(**_: Any) -> StubMemoryManager:
        return manager

    monkeypatch.setattr("neuroca.cli.commands.memory.create_memory_system", _factory)
    return manager


def test_seed_memories_seeds_entries(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    manager = StubMemoryManager()

    def _factory(**_: Any) -> StubMemoryManager:
        return manager

    monkeypatch.setattr("neuroca.cli.commands.memory.create_memory_system", _factory)

    seed_file = tmp_path / "memories.json"
    seed_file.write_text(json.dumps([
        {"content": "First memory"},
        {"content": "Second memory", "importance": 0.25},
    ]))

    result = runner.invoke(
        memory_app,
        ["seed", str(seed_file), "--tier", "stm", "--user", "user-123"],
    )

    assert result.exit_code == 0
    assert len(manager.add_calls) == 2
    assert manager.add_calls[0]["metadata"]["user_id"] == "user-123"
    assert "Seeded 2 memories successfully" in result.stdout


def test_inspect_memories_displays_results(stub_manager: StubMemoryManager) -> None:
    result = runner.invoke(memory_app, ["inspect", "--tier", "stm", "--limit", "5"])

    assert result.exit_code == 0
    assert stub_manager.search_calls[0]["limit"] == 5
    assert "Alpha summary" in result.stdout


def test_consolidate_memory_invokes_manager(stub_manager: StubMemoryManager) -> None:
    result = runner.invoke(
        memory_app,
        [
            "consolidate",
            "mem-9",
            "--source",
            "stm",
            "--target",
            "ltm",
            "--tag",
            "reviewed",
        ],
    )

    assert result.exit_code == 0
    call = stub_manager.consolidate_calls[0]
    assert call["memory_id"] == "mem-9"
    assert call["target_tier"] == "ltm"
    assert call["metadata"]["tags"]["reviewed"] is True


def test_reindex_vector_store_rebuilds_index(stub_manager: StubMemoryManager) -> None:
    result = runner.invoke(
        memory_app,
        ["reindex", "--id", "mem-1", "--full-refresh"],
    )

    assert result.exit_code == 0
    call = stub_manager.vector_backend.reindex_calls[0]
    assert call["target_ids"] == ["mem-1"]
    assert call["full_refresh"] is True
    assert "Vector Index Integrity" in result.stdout


def test_sample_packs_list_displays_available_packs() -> None:
    result = runner.invoke(memory_app, ["sample-packs", "list"])

    assert result.exit_code == 0
    assert "Memory Sample Packs" in result.stdout
    assert "collaborative-brainstorm" in result.stdout
    assert "customer-support-playbook" in result.stdout
    assert "--user team-alpha" in result.stdout


def test_sample_packs_export_writes_file(tmp_path: Path) -> None:
    output_path = tmp_path / "packs"

    result = runner.invoke(
        memory_app,
        ["sample-packs", "export", "customer-support-playbook", "--output", str(output_path)],
    )

    assert result.exit_code == 0
    assert output_path.exists()
    contents = output_path.read_text(encoding="utf-8")
    assert "Post-mortem" in contents
