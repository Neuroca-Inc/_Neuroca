from __future__ import annotations

from typer.testing import CliRunner
import pytest

# Import the CLI module and app to test
import neuroca.cli.commands.llm as cli_llm
from neuroca.cli.commands.llm import llm_app


class _FakeResponse:
    def __init__(self, content: str = "ok", provider: str = "ollama", model: str = "gemma3:4b"):
        self.content = content
        self.provider = provider
        self.model = model
        self.usage = None
        self.elapsed_time = 0.01
        self.metadata = {}


class _FakeManager:
    def __init__(self, *args, **kwargs):
        pass

    async def query(self, **kwargs):
        return _FakeResponse()

    async def close(self):
        return None


def test_llm_query_cli_smoke(monkeypatch: pytest.MonkeyPatch):
    """
    Smoke test for `neuroca llm query` using a patched manager to avoid external deps.
    """
    runner = CliRunner()

    async def _fake_get_managers(config: dict):
        return _FakeManager(), {}

    monkeypatch.setattr(cli_llm, "get_managers", _fake_get_managers, raising=True)

    result = runner.invoke(
        llm_app,
        [
            "query",
            "hello from cli",
            "--provider",
            "ollama",
            "--model",
            "gemma3:4b",
            "--no-memory",
            "--no-health",
            "--no-goals",
            "--format",
            "text",
        ],
    )

    # Typer returns Exit code 0 on success; ensure our patched flow prints the response content
    assert result.exit_code == 0, f"stderr/stdout:\n{result.stdout}\n{result.stderr}"
    assert "ok" in result.stdout.lower()


def test_llm_bench_cli_smoke(monkeypatch: pytest.MonkeyPatch):
    """
    Smoke test for `neuroca llm bench` latency suite using a patched manager.
    """
    # Patch the manager used inside the bench command
    monkeypatch.setattr(cli_llm, "LLMIntegrationManager", _FakeManager, raising=True)

    runner = CliRunner()
    result = runner.invoke(
        llm_app,
        [
            "bench",
            "--provider",
            "ollama",
            "--model",
            "gemma3:4b",
            "--suite",
            "latency",
            "--runs",
            "3",
            "--concurrency",
            "1",
            "--pretty",
        ],
    )

    assert result.exit_code == 0, f"stderr/stdout:\n{result.stdout}\n{result.stderr}"
    # Expect JSON output with a latency result
    assert '"name": "latency"' in result.stdout or '"latency"' in result.stdout.lower()