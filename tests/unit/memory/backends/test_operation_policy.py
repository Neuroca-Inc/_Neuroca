from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional

import pytest

from neuroca.memory.backends.base.core import BaseStorageBackend
from neuroca.memory.backends.factory import BackendType, MemoryTier, StorageBackendFactory
from neuroca.memory.backends.policies import BackendOperationPolicy, RetryPolicy
from neuroca.memory.exceptions import StorageOperationError


class _RecordingBackend(BaseStorageBackend):
    """Minimal backend implementation that records policy configuration."""

    def __init__(self, **kwargs: Any):
        super().__init__()
        self.kwargs = kwargs
        self._created: int = 0

    async def _initialize_backend(self) -> None:  # pragma: no cover - trivial
        return None

    async def _shutdown_backend(self) -> None:  # pragma: no cover - trivial
        return None

    async def _get_backend_stats(self) -> Dict[str, Any]:  # pragma: no cover - trivial
        return {}

    async def _create_item(self, item_id: str, data: Dict[str, Any]) -> bool:
        self._created += 1
        return True

    async def _read_item(self, item_id: str) -> Optional[Dict[str, Any]]:  # pragma: no cover - unused in tests
        return {}

    async def _update_item(self, item_id: str, data: Dict[str, Any]) -> bool:  # pragma: no cover - unused in tests
        return True

    async def _delete_item(self, item_id: str) -> bool:  # pragma: no cover - unused in tests
        return True

    async def _item_exists(self, item_id: str) -> bool:  # pragma: no cover - unused in tests
        return False

    async def _query_items(self, *args: Any, **kwargs: Any) -> list[Dict[str, Any]]:  # pragma: no cover - unused
        return []

    async def _count_items(self, filters: Optional[Dict[str, Any]] = None) -> int:  # pragma: no cover - unused
        return 0

    async def _clear_all_items(self) -> bool:  # pragma: no cover - unused
        return True


class _FlakyBackend(_RecordingBackend):
    """Test double that fails a configurable number of times before succeeding."""

    def __init__(self, failures: int = 0, **kwargs: Any):
        super().__init__(**kwargs)
        self._remaining_failures = failures

    async def _create_item(self, item_id: str, data: Dict[str, Any]) -> bool:
        self._created += 1
        if self._remaining_failures > 0:
            self._remaining_failures -= 1
            raise StorageOperationError(
                operation="create",
                backend_type="_FlakyBackend",
                message="forced failure",
            )
        return True


class _SlowBackend(_RecordingBackend):
    async def _create_item(self, item_id: str, data: Dict[str, Any]) -> bool:
        await asyncio.sleep(0.05)
        return await super()._create_item(item_id, data)


async def _shutdown_instance(instance_name: str, backend: BaseStorageBackend) -> None:
    try:
        await backend.shutdown()
    finally:
        StorageBackendFactory._instances.pop(instance_name, None)


@pytest.mark.asyncio
async def test_storage_factory_assigns_default_vector_policy(tmp_path) -> None:
    instance_name = "policy-vector"
    backend = StorageBackendFactory.create_storage(
        tier=MemoryTier.LTM,
        backend_type=BackendType.VECTOR,
        config={"dimension": 3, "index_path": str(tmp_path / "vector.json")},
        use_existing=False,
        instance_name=instance_name,
    )

    try:
        assert backend.operation_policy.timeout_seconds == pytest.approx(6.0)
        assert backend.operation_policy.retry.attempts == 3
    finally:
        await _shutdown_instance(instance_name, backend)


@pytest.mark.asyncio
async def test_storage_factory_respects_policy_overrides(tmp_path) -> None:
    instance_name = "policy-vector-override"
    backend = StorageBackendFactory.create_storage(
        tier=MemoryTier.LTM,
        backend_type=BackendType.VECTOR,
        config={
            "dimension": 3,
            "index_path": str(tmp_path / "vector.json"),
            "operation_policy": {
                "timeout_seconds": 0.25,
                "retry": {"attempts": 2, "initial_delay_seconds": 0.01, "backoff_multiplier": 1.0},
            },
        },
        use_existing=False,
        instance_name=instance_name,
    )

    try:
        assert backend.operation_policy.timeout_seconds == pytest.approx(0.25)
        assert backend.operation_policy.retry.attempts == 2
        assert backend.operation_policy.retry.initial_delay_seconds == pytest.approx(0.01)
    finally:
        await _shutdown_instance(instance_name, backend)


@pytest.mark.asyncio
async def test_storage_factory_updates_policy_for_reused_instance(tmp_path) -> None:
    instance_name = "policy-vector-reuse"
    base_config = {"dimension": 3, "index_path": str(tmp_path / "vector.json")}
    backend = StorageBackendFactory.create_storage(
        tier=MemoryTier.LTM,
        backend_type=BackendType.VECTOR,
        config=base_config,
        instance_name=instance_name,
    )

    override = StorageBackendFactory.create_storage(
        tier=MemoryTier.LTM,
        backend_type=BackendType.VECTOR,
        config={
            **base_config,
            "operation_policy": {
                "timeout_seconds": 0.2,
                "retry_attempts": 4,
                "retry_initial_delay_seconds": 0.02,
            },
        },
        instance_name=instance_name,
    )

    try:
        assert backend is override
        assert backend.operation_policy.timeout_seconds == pytest.approx(0.2)
        assert backend.operation_policy.retry.attempts == 4
        assert backend.operation_policy.retry.initial_delay_seconds == pytest.approx(0.02)
    finally:
        await _shutdown_instance(instance_name, backend)


@pytest.mark.asyncio
async def test_storage_factory_assigns_default_sql_policy(monkeypatch) -> None:
    instance_name = "policy-sql"
    monkeypatch.setitem(StorageBackendFactory._backend_registry, BackendType.SQL, _RecordingBackend)

    backend = StorageBackendFactory.create_storage(
        tier=MemoryTier.LTM,
        backend_type=BackendType.SQL,
        config={"dsn": "postgresql://example"},
        use_existing=False,
        instance_name=instance_name,
    )

    assert backend.operation_policy.timeout_seconds == pytest.approx(10.0)
    assert backend.operation_policy.retry.attempts == 4
    StorageBackendFactory._instances.pop(instance_name, None)


@pytest.mark.asyncio
async def test_storage_factory_assigns_default_redis_policy(monkeypatch) -> None:
    instance_name = "policy-redis"
    monkeypatch.setitem(StorageBackendFactory._backend_registry, BackendType.REDIS, _RecordingBackend)

    backend = StorageBackendFactory.create_storage(
        tier=MemoryTier.STM,
        backend_type=BackendType.REDIS,
        config={"host": "localhost", "port": 6379},
        use_existing=False,
        instance_name=instance_name,
    )

    assert backend.operation_policy.timeout_seconds == pytest.approx(2.5)
    assert backend.operation_policy.retry.attempts == 5
    StorageBackendFactory._instances.pop(instance_name, None)


@pytest.mark.asyncio
async def test_backend_policy_retries_failures() -> None:
    backend = _FlakyBackend(failures=2)
    backend.configure_operation_policy(
        BackendOperationPolicy(timeout_seconds=0.5, retry=RetryPolicy(attempts=3, initial_delay_seconds=0.0))
    )

    await backend.initialize()

    try:
        assert await backend.create("memory-id", {"value": 1}) is True
        assert backend._created == 3
    finally:
        await backend.shutdown()


@pytest.mark.asyncio
async def test_backend_policy_enforces_timeout() -> None:
    backend = _SlowBackend()
    backend.configure_operation_policy(
        BackendOperationPolicy(timeout_seconds=0.01, retry=RetryPolicy(attempts=1))
    )

    await backend.initialize()

    try:
        with pytest.raises(StorageOperationError) as excinfo:
            await backend.create("slow-memory", {"value": 1})
        assert "timed out" in str(excinfo.value)
    finally:
        await backend.shutdown()
