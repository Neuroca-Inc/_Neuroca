"""Tests for the memory system factory wiring with storage backends."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import pytest

from neuroca.config.settings import get_settings
from neuroca.memory.backends.factory import BackendType, MemoryTier, StorageBackendFactory
from neuroca.memory.factory import create_memory_system


@dataclass
class _StubBackend:
    """Lightweight backend stub that captures factory inputs."""

    tier: Optional[MemoryTier]
    backend_type: Optional[BackendType]
    config: Optional[Dict[str, Any]]

    initialized: bool = False

    async def initialize(self) -> None:  # pragma: no cover - unused, defensive completeness
        self.initialized = True

    async def shutdown(self) -> None:  # pragma: no cover - unused, defensive completeness
        self.initialized = False


@pytest.fixture
def storage_factory_spy(monkeypatch: pytest.MonkeyPatch) -> Dict[str, Any]:
    """Patch the storage factory to capture tier construction arguments."""

    calls: List[Dict[str, Any]] = []
    backends: Dict[MemoryTier, _StubBackend] = {}

    def _fake_create_storage(
        cls,
        *,
        tier: Optional[MemoryTier] = None,
        backend_type: Optional[BackendType] = None,
        config: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> _StubBackend:
        backend = _StubBackend(tier=tier, backend_type=backend_type, config=config)
        calls.append({
            "tier": tier,
            "backend_type": backend_type,
            "config": config,
        })
        if tier is not None:
            backends[tier] = backend
        return backend

    monkeypatch.setattr(
        StorageBackendFactory,
        "create_storage",
        classmethod(_fake_create_storage),
    )

    return {
        "calls": calls,
        "backends": backends,
    }


@pytest.fixture(autouse=True)
def reset_settings_cache() -> None:
    """Ensure each test observes a clean configuration state."""

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_create_memory_system_constructs_each_tier_via_storage_factory(storage_factory_spy: Dict[str, Any]) -> None:
    """Factory should instantiate every tier through the storage factory."""

    spy_calls = storage_factory_spy["calls"]
    backends = storage_factory_spy["backends"]

    manager = create_memory_system()

    assert [call["tier"] for call in spy_calls] == [
        MemoryTier.STM,
        MemoryTier.MTM,
        MemoryTier.LTM,
    ]
    assert all(call["backend_type"] is None for call in spy_calls)

    call_map = {entry["tier"]: entry for entry in spy_calls}
    assert call_map[MemoryTier.STM]["config"] is None
    assert call_map[MemoryTier.MTM]["config"] is None
    assert call_map[MemoryTier.LTM]["config"] == {"dimension": manager.embedding_dimension}

    assert manager._stm_instance._backend is backends[MemoryTier.STM]
    assert manager._mtm_instance._backend is backends[MemoryTier.MTM]
    assert manager._ltm_instance._backend is backends[MemoryTier.LTM]

    assert manager._config["stm"] == {}
    assert manager._config["mtm"] == {}
    assert manager._config["ltm"].get("embedding_dimension") == manager.embedding_dimension


def test_create_memory_system_applies_overrides_and_shared_storage(storage_factory_spy: Dict[str, Any]) -> None:
    """Global, per-tier, and shared storage configuration should propagate correctly."""

    spy_calls = storage_factory_spy["calls"]
    backends = storage_factory_spy["backends"]

    config = {
        "maintenance_interval": 120,
        "storage": {"region": "us-east-1", "options": {"timeout": 10}},
        "backend_types": {"mtm": "sql"},
        "stm": {
            "storage": {"host": "stm.local", "options": {"timeout": 5}},
            "max_items": 123,
        },
        "mtm": {
            "storage": {"database": "mtm.db"},
            "window": 7,
        },
        "ltm": {
            "backend_type": "memory",
            "storage": {"options": {"timeout": 30}, "table": "ltm_table"},
            "retention_days": 30,
        },
    }

    manager = create_memory_system(backend_type="sqlite", config=config)

    call_map = {entry["tier"]: entry for entry in spy_calls}
    assert set(call_map) == {MemoryTier.STM, MemoryTier.MTM, MemoryTier.LTM}

    assert call_map[MemoryTier.STM]["backend_type"] == BackendType.SQLITE
    assert call_map[MemoryTier.MTM]["backend_type"] == BackendType.SQL
    assert call_map[MemoryTier.LTM]["backend_type"] == BackendType.MEMORY

    assert call_map[MemoryTier.STM]["config"] == {
        "region": "us-east-1",
        "options": {"timeout": 5},
        "host": "stm.local",
    }
    assert call_map[MemoryTier.MTM]["config"] == {
        "region": "us-east-1",
        "options": {"timeout": 10},
        "database": "mtm.db",
    }
    expected_dimension = manager.embedding_dimension
    assert call_map[MemoryTier.LTM]["config"] == {
        "region": "us-east-1",
        "options": {"timeout": 30},
        "table": "ltm_table",
        "dimension": expected_dimension,
    }

    assert manager._stm_instance._backend is backends[MemoryTier.STM]
    assert manager._mtm_instance._backend is backends[MemoryTier.MTM]
    assert manager._ltm_instance._backend is backends[MemoryTier.LTM]

    assert manager._stm_storage_type == BackendType.SQLITE
    assert manager._mtm_storage_type == BackendType.SQL
    assert manager._ltm_storage_type == BackendType.MEMORY

    assert manager._backend_config == {"region": "us-east-1", "options": {"timeout": 10}}
    assert manager._config["maintenance_interval"] == 120
    assert manager._config["stm"]["max_items"] == 123
    assert manager._config["mtm"]["window"] == 7
    assert manager._config["ltm"]["retention_days"] == 30
    assert manager._config["ltm"]["embedding_dimension"] == expected_dimension


def test_create_memory_system_uses_vector_dimension_override(storage_factory_spy: Dict[str, Any]) -> None:
    """Vector overrides should define the active embedding dimension."""

    spy_calls = storage_factory_spy["calls"]

    manager = create_memory_system(
        config={
            "backend_types": {"ltm": BackendType.VECTOR.value},
            "ltm": {"storage": {"dimension": 42}},
        }
    )

    call_map = {entry["tier"]: entry for entry in spy_calls}
    assert call_map[MemoryTier.LTM]["config"]["dimension"] == 42
    assert manager.embedding_dimension == 42


def test_create_memory_system_conflicting_embedding_dimension_raises(
    storage_factory_spy: Dict[str, Any]
) -> None:
    """Mismatched configuration sources should raise a ConfigurationError."""

    with pytest.raises(RuntimeError) as exc:
        create_memory_system(
            config={"ltm": {"storage": {"dimension": 24}}},
            embedding_dimension=12,
        )

    assert "Conflicting embedding dimension configuration" in str(exc.value)


def test_create_memory_system_rejects_out_of_range_threshold(storage_factory_spy: Dict[str, Any]) -> None:
    """Tier threshold overrides outside expected bounds should fail validation."""

    with pytest.raises(RuntimeError) as exc:
        create_memory_system(config={"stm": {"consolidation_threshold": 0}})

    assert "consolidation threshold" in str(exc.value)


def test_create_memory_system_requires_schema_fields(storage_factory_spy: Dict[str, Any]) -> None:
    """Schema configuration must include required tables when provided."""

    config = {
        "storage": {"schema": {"metadata_table": "", "content_table": "mem_content"}},
    }

    with pytest.raises(RuntimeError) as exc:
        create_memory_system(config=config)

    assert "schema" in str(exc.value)
    assert "metadata_table" in str(exc.value)


def test_create_memory_system_detects_settings_embedding_conflict(
    storage_factory_spy: Dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Conflicts between environment-provided dimensions and config should raise errors."""

    monkeypatch.setenv("NCA_LONG_TERM_MEMORY_EMBEDDING_DIMENSIONS", "64")

    try:
        with pytest.raises(RuntimeError) as exc:
            create_memory_system(config={"ltm": {"storage": {"dimension": 128}}})
    finally:
        get_settings.cache_clear()

    assert "Conflicting embedding dimension configuration" in str(exc.value)
