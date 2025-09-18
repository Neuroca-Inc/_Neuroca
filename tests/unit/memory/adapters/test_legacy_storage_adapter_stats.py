"""Tests for the legacy storage adapter statistics fallback."""

from __future__ import annotations

import importlib
from types import SimpleNamespace

import pytest

from neuroca.memory.interfaces import StorageStats


class FailingBackend:
    async def get_stats(self) -> StorageStats:
        raise RuntimeError("boom")


@pytest.mark.asyncio()
async def test_get_stats_returns_placeholder_when_backend_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    search_module = importlib.import_module("neuroca.memory.models.search")
    if not hasattr(search_module, "SearchFilter"):
        monkeypatch.setattr(search_module, "SearchFilter", SimpleNamespace, raising=False)
    if not hasattr(search_module, "SearchResult"):
        monkeypatch.setattr(search_module, "SearchResult", SimpleNamespace, raising=False)

    module = importlib.import_module("neuroca.memory.adapters.storage_adapters")
    LegacyLTMStorageAdapter = module.LegacyLTMStorageAdapter

    adapter = LegacyLTMStorageAdapter()
    adapter.backend = FailingBackend()
    adapter._initialized = True

    stats = await adapter.get_stats()

    assert isinstance(stats, StorageStats)
    assert stats.backend_type == "FailingBackend"
    assert stats.item_count == 0
    assert stats.additional_info == {"error": "boom"}
