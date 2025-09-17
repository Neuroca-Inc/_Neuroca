"""Tests for the LLM API route dependency wiring."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from neuroca.api.routes import llm


class _StubMemoryManager:
    """Minimal async memory manager stub tracking lifecycle calls."""

    def __init__(self) -> None:
        self.initialized = False
        self.shutdown_called = False

    async def initialize(self) -> None:
        self.initialized = True

    async def shutdown(self) -> None:
        self.shutdown_called = True


class _BaseStubIntegrationManager:
    """Shared implementation for spying on integration manager usage."""

    def __init__(self, *, config: dict[str, object], memory_manager, health_manager, goal_manager) -> None:
        self.config = config
        self.memory_manager = memory_manager
        self.health_manager = health_manager
        self.goal_manager = goal_manager
        self.closed = False
        self.query_calls: list[dict[str, object]] = []
        self.memory_state_during_query: list[bool | None] = []

    async def close(self) -> None:
        self.closed = True


class _SuccessfulIntegrationManager(_BaseStubIntegrationManager):
    async def query(self, **kwargs):
        self.query_calls.append(kwargs)
        self.memory_state_during_query.append(getattr(self.memory_manager, "initialized", None))
        return SimpleNamespace(
            content="stub-response",
            provider="stub-provider",
            model="stub-model",
            usage=None,
            elapsed_time=0.123,
            metadata={"memory_initialized": self.memory_state_during_query[-1]},
        )


class _FailingIntegrationManager(_BaseStubIntegrationManager):
    async def query(self, **kwargs):
        self.query_calls.append(kwargs)
        self.memory_state_during_query.append(getattr(self.memory_manager, "initialized", None))
        raise RuntimeError("boom")


def _build_test_app() -> TestClient:
    app = FastAPI()
    app.include_router(llm.router)
    return TestClient(app)


def test_query_route_initializes_and_closes_memory_manager(monkeypatch: pytest.MonkeyPatch) -> None:
    created_managers: list[_StubMemoryManager] = []
    integration_instances: list[_SuccessfulIntegrationManager] = []

    def _create_stub_memory_system(*args, **kwargs):
        manager = _StubMemoryManager()
        created_managers.append(manager)
        return manager

    def _capture_integration(**kwargs):
        instance = _SuccessfulIntegrationManager(**kwargs)
        integration_instances.append(instance)
        return instance

    monkeypatch.setattr(llm, "create_memory_system", _create_stub_memory_system)
    monkeypatch.setattr(llm, "LLMIntegrationManager", _capture_integration)

    client = _build_test_app()

    response = client.post(
        "/llm/query",
        json={"prompt": "hello", "memory_context": True},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["content"] == "stub-response"

    assert created_managers, "memory manager should be constructed"
    manager = created_managers[0]
    assert manager.initialized is True
    assert manager.shutdown_called is True

    assert integration_instances, "integration manager should be created"
    integration = integration_instances[0]
    assert integration.closed is True
    assert integration.memory_state_during_query == [True]
    assert integration.query_calls[0]["memory_context"] is True


def test_query_route_closes_resources_on_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    created_managers: list[_StubMemoryManager] = []
    integration_instances: list[_FailingIntegrationManager] = []

    def _create_stub_memory_system(*args, **kwargs):
        manager = _StubMemoryManager()
        created_managers.append(manager)
        return manager

    def _capture_integration(**kwargs):
        instance = _FailingIntegrationManager(**kwargs)
        integration_instances.append(instance)
        return instance

    monkeypatch.setattr(llm, "create_memory_system", _create_stub_memory_system)
    monkeypatch.setattr(llm, "LLMIntegrationManager", _capture_integration)

    client = _build_test_app()

    response = client.post(
        "/llm/query",
        json={"prompt": "fail", "memory_context": True},
    )

    assert response.status_code == 502
    detail = response.json()["detail"]
    assert "LLM query failed" in detail

    assert created_managers, "memory manager should be constructed"
    manager = created_managers[0]
    assert manager.initialized is True
    assert manager.shutdown_called is True

    assert integration_instances, "integration manager should be created"
    integration = integration_instances[0]
    assert integration.closed is True
    assert integration.memory_state_during_query == [True]
