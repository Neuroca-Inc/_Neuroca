from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import pytest

from neuroca.memory.manager.memory_manager import MemoryManager


@dataclass
class _StubTier:
    name: str
    query_results: List[Dict[str, Any]] = field(default_factory=list)
    promotion_candidates: List[Dict[str, Any]] = field(default_factory=list)
    storage: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    maintenance_calls: int = 0

    async def initialize(self) -> None:
        return None

    async def shutdown(self) -> None:
        return None

    async def run_maintenance(self) -> Dict[str, Any]:
        self.maintenance_calls += 1
        return {"tier": self.name, "runs": self.maintenance_calls}

    async def store(self, payload: Dict[str, Any], memory_id: Optional[str] = None) -> str:
        memory_id = memory_id or payload.get("id") or f"{self.name}-{len(self.storage)}"
        stored = dict(payload)
        stored.setdefault("id", memory_id)
        metadata = stored.setdefault("metadata", {})
        metadata.setdefault("tags", {})
        metadata["tier"] = self.name
        self.storage[memory_id] = stored
        return memory_id

    async def retrieve(self, memory_id: str) -> Optional[Dict[str, Any]]:
        return self.storage.get(memory_id)

    async def delete(self, memory_id: str) -> bool:
        return self.storage.pop(memory_id, None) is not None

    async def query(self, filters: Optional[Dict[str, Any]] = None, limit: Optional[int] = None):
        return list(self.query_results)

    async def get_promotion_candidates(self, limit: int = 10) -> List[Dict[str, Any]]:
        return list(self.promotion_candidates)


@pytest.mark.asyncio
async def test_run_maintenance_promotes_candidates_between_tiers():
    stm = _StubTier("stm")
    mtm = _StubTier("mtm")
    ltm = _StubTier("ltm")

    manager = MemoryManager(
        config={"maintenance_interval": 0, "stm": {}, "mtm": {}, "ltm": {}},
        stm=stm,
        mtm=mtm,
        ltm=ltm,
    )

    await manager.initialize()
    try:
        await stm.store(
            {
                "id": "stm-candidate",
                "content": {"text": "short term"},
                "metadata": {
                    "status": "active",
                    "tags": {},
                    "importance": 0.9,
                    "access_count": 6,
                },
                "access_count": 6,
            }
        )
        stm.query_results = [
            {
                "id": "stm-candidate",
                "metadata": {"importance": 0.9, "tags": {}},
                "access_count": 6,
            }
        ]

        await mtm.store(
            {
                "id": "mtm-candidate",
                "content": {"text": "medium term"},
                "metadata": {"status": "active", "tags": {"promote_to_ltm": True}},
            }
        )
        mtm.promotion_candidates = [{"id": "mtm-candidate"}]

        results = await manager.run_maintenance()

        assert results["status"] == "ok"
        assert results["consolidated_memories"] == 2
        assert set(results["tiers"].keys()) == {"stm", "mtm", "ltm"}
        assert "telemetry" in results

        assert "stm-candidate" not in stm.storage
        assert "stm-candidate" in mtm.storage

        assert "mtm-candidate" not in mtm.storage
        assert "mtm-candidate" in ltm.storage
    finally:
        await manager.shutdown()
