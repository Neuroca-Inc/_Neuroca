import pytest

from neuroca.memory.manager.capacity_pressure import TierCapacityPressureAdapter
from neuroca.memory.manager.maintenance import MaintenanceOrchestrator
from neuroca.memory.manager.memory_manager import MemoryManager


class _StubTier:
    def __init__(self, name: str, *, count: int = 0, capacity: int | None = None) -> None:
        self.name = name
        self._count = count
        self._capacity = capacity
        self.config = {"max_capacity": capacity} if capacity is not None else {}
        self.query_results = []

    async def initialize(self) -> None:  # pragma: no cover - simple stub
        return None

    async def shutdown(self) -> None:  # pragma: no cover - simple stub
        return None

    async def count(self, _filters=None) -> int:
        return self._count

    async def query(self, filters=None, limit=None):  # pragma: no cover - compatibility
        del filters, limit
        return list(self.query_results)


@pytest.mark.asyncio
async def test_capacity_refresh_records_pressure_from_counts() -> None:
    manager = MemoryManager(
        config={"maintenance_interval": 0, "resource_limits": {}},
        stm=_StubTier("stm", count=90, capacity=100),
        mtm=_StubTier("mtm", count=20, capacity=200),
        ltm=_StubTier("ltm", count=5, capacity=400),
    )
    await manager.initialize()
    try:
        await manager._refresh_capacity_pressure()
        snapshot = manager._capacity_adapter.snapshot()
        stm_pressure = snapshot["stm"]["pressure"]
        assert stm_pressure > 0.0
        assert snapshot["mtm"]["pressure"] == pytest.approx(0.0)
    finally:
        await manager.shutdown()


def test_pressure_adapter_scales_thresholds_and_batches() -> None:
    adapter = TierCapacityPressureAdapter(relief_ratio=0.5, saturation_ratio=0.8, smoothing=1.0)
    base_threshold = 0.6
    assert adapter.stm_priority_threshold(base_threshold) == pytest.approx(base_threshold)
    adapter.observe("stm", 0.8)
    lowered = adapter.stm_priority_threshold(base_threshold)
    assert lowered < base_threshold
    assert lowered >= 0.35
    assert adapter.stm_batch_size(5) > 5
    adapter.observe("mtm", 0.9)
    assert adapter.mtm_batch_size(10) > 10


@pytest.mark.asyncio
async def test_adaptive_threshold_includes_lower_priority_candidates() -> None:
    tiers = {name: _StubTier(name, capacity=100) for name in ("stm", "mtm", "ltm")}
    manager = MemoryManager(
        config={"maintenance_interval": 0, "resource_limits": {}},
        stm=tiers["stm"],
        mtm=tiers["mtm"],
        ltm=tiers["ltm"],
    )
    await manager.initialize()
    orchestrator = MaintenanceOrchestrator(manager, min_interval=5.0)
    manager._maintenance_orchestrator = orchestrator

    tiers["stm"].query_results = [
        {
            "id": "high",
            "metadata": {"importance": 0.9, "tags": {}},
            "access_count": 4,
        },
        {
            "id": "mid",
            "metadata": {"importance": 0.55, "tags": {}},
            "access_count": 12,
        },
    ]

    try:
        baseline = await orchestrator._collect_stm_candidates(
            tiers["stm"], limit=5, errors=[]
        )
        assert [item["id"] for item in baseline] == ["high"]

        manager._capacity_adapter.observe("stm", 0.92)
        expanded = await orchestrator._collect_stm_candidates(
            tiers["stm"], limit=5, errors=[]
        )
        assert {item["id"] for item in expanded} == {"high", "mid"}
    finally:
        await manager.shutdown()
