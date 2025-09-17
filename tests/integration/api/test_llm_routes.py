from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any, Dict, List

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from neuroca.api.routes import llm


class _StubMemoryManager:
    def __init__(self) -> None:
        self.initialized = False
        self.shutdown_called = False

    async def initialize(self) -> None:
        self.initialized = True

    async def shutdown(self) -> None:
        self.shutdown_called = True


class _RecordingIntegrationManager:
    def __init__(self, *, config: Dict[str, Any], memory_manager, health_manager, goal_manager) -> None:
        self.config = config
        self.memory_manager = memory_manager
        self.health_manager = health_manager
        self.goal_manager = goal_manager
        self.query_calls: List[Dict[str, Any]] = []
        self.closed = False

    async def query(self, **kwargs: Any) -> SimpleNamespace:
        self.query_calls.append(kwargs)
        return SimpleNamespace(
            content="integration-response",
            provider="stub-provider",
            model="stub-model",
            usage={"total_tokens": 42},
            elapsed_time=0.25,
            metadata={"memory_initialized": getattr(self.memory_manager, "initialized", None)},
        )

    async def _retrieve_relevant_memories(self, prompt: str) -> List[Dict[str, Any]]:
        return [{"content": f"memory hit for {prompt}"}]

    async def close(self) -> None:
        self.closed = True


def _build_test_client() -> TestClient:
    app = FastAPI()
    app.include_router(llm.router)
    return TestClient(app)


def test_query_route_returns_structured_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    memory_manager = _StubMemoryManager()
    managers: List[_StubMemoryManager] = []
    integrations: List[_RecordingIntegrationManager] = []

    def _create_stub_memory_system(*args: Any, **kwargs: Any):
        managers.append(memory_manager)
        return memory_manager

    def _capture_integration(**kwargs: Any):
        mgr = _RecordingIntegrationManager(**kwargs)
        integrations.append(mgr)
        return mgr

    monkeypatch.setattr(llm, "create_memory_system", _create_stub_memory_system)
    monkeypatch.setattr(llm, "LLMIntegrationManager", _capture_integration)

    client = _build_test_client()
    response = client.post(
        "/llm/query",
        json={"prompt": "integration test", "memory_context": True},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["content"] == "integration-response"
    assert payload["provider"] == "stub-provider"
    assert payload["model"] == "stub-model"
    assert payload["metadata"]["memory_initialized"] is True

    assert managers and managers[0].initialized is True
    assert managers[0].shutdown_called is True

    assert integrations and integrations[0].closed is True
    assert integrations[0].query_calls[0]["memory_context"] is True


def test_stream_route_emits_meta_and_token_events(monkeypatch: pytest.MonkeyPatch) -> None:
    integrations: List[_RecordingIntegrationManager] = []

    def _capture_integration(**kwargs: Any):
        mgr = _RecordingIntegrationManager(**kwargs)
        integrations.append(mgr)
        return mgr

    monkeypatch.setattr(llm, "LLMIntegrationManager", _capture_integration)
    monkeypatch.setattr(llm, "create_memory_system", lambda *a, **k: None)

    client = _build_test_client()
    with client.stream(
        "GET",
        "/llm/stream",
        params={"prompt": "stream test", "provider": "custom"},
    ) as response:
        assert response.status_code == 200
        lines = [line.decode("utf-8") if isinstance(line, bytes) else line for line in response.iter_lines() if line]

    events = [json.loads(line.split("data: ", 1)[1]) for line in lines if line.startswith("data:")]
    assert events[0]["type"] == "meta"
    assert events[0]["provider"] == "custom"
    assert events[-1]["type"] == "end"
    assert any(event["type"] == "token" for event in events)

    assert integrations and integrations[0].closed is True
    assert integrations[0].query_calls, "stream fallback should invoke query once"
