import json
import pytest

from neuroca.integration.manager import LLMIntegrationManager
import neuroca.integration.adapters.ollama as ollama_module
from neuroca.integration.prompts.templates import TemplateManager
from neuroca.integration.models import LLMResponse


class _RespCM:
    """Async context manager wrapper returning a prepared FakeResponse."""
    def __init__(self, resp):
        self._resp = resp

    async def __aenter__(self):
        return self._resp

    async def __aexit__(self, exc_type, exc, tb):
        return False


class FakeResponse:
    """Mimics aiohttp response object for JSON/text and status code."""
    def __init__(self, status: int, json_data: dict, text_data: str | None = None):
        self.status = status
        self._json_data = json_data
        self._text_data = text_data or json.dumps(json_data)

    async def json(self):
        return self._json_data

    async def text(self):
        return self._text_data


class FakeSession:
    """Mimics aiohttp.ClientSession with post/get used by OllamaAdapter."""
    def __init__(self, *args, **kwargs):
        self.closed = False

    async def close(self):
        self.closed = True

    def post(self, url: str, json: dict):
        # Generation endpoint
        if url.endswith("/api/generate"):
            resp = FakeResponse(
                200,
                {
                    "response": "Hello from Manager via Ollama",
                    "eval_count": 7,
                    "prompt_eval_count": 4,
                    "total_duration": 999,
                    "model": json.get("model", "gemma3:4b"),
                },
            )
            return _RespCM(resp)
        # Embeddings endpoint
        if url.endswith("/api/embeddings"):
            resp = FakeResponse(200, {"embedding": [0.11, 0.22, 0.33]})
            return _RespCM(resp)
        return _RespCM(FakeResponse(404, {"error": "not found"}))

    def get(self, url: str):
        # Tags endpoint
        if url.endswith("/api/tags"):
            resp = FakeResponse(200, {"models": [{"name": "gemma3:4b"}]})
            return _RespCM(resp)
        return _RespCM(FakeResponse(404, {"error": "not found"}))


@pytest.mark.asyncio
async def test_manager_query_with_ollama(monkeypatch):
    """
    End-to-end smoke test: LLMIntegrationManager.query routes to OllamaAdapter and returns LLMResponse.
    """
    # Avoid dependency on Jinja/real template content: render base prompt as-is.
    monkeypatch.setattr(TemplateManager, "render_template", lambda self, tid, variables=None: (variables or {}).get("base_prompt", ""))

    # Patch aiohttp session in ollama adapter
    monkeypatch.setattr(ollama_module.aiohttp, "ClientSession", FakeSession)

    config = {
        "default_provider": "ollama",
        "default_model": "gemma3:4b",
        "providers": {
            "ollama": {
                "base_url": "http://localhost:11434",
                "default_model": "gemma3:4b",
                "request_timeout": 30,
                "max_retries": 1,
            }
        },
        # Ensure the TemplateManager default path isn't required
        "prompt_template_dirs": [],
        "store_interactions": False,
    }

    mgr = LLMIntegrationManager(config=config)

    try:
        resp: LLMResponse = await mgr.query(
            prompt="Say hello",
            provider="ollama",
            model="gemma3:4b",
            memory_context=False,
            health_aware=False,
            goal_directed=False,
            max_tokens=64,
            temperature=0.3,
        )
        assert isinstance(resp, LLMResponse)
        assert isinstance(resp.content, str)
        assert "Hello" in resp.content or "hello" in resp.content
        assert resp.model == "gemma3:4b"
        assert resp.provider == "ollama"

        # Metrics sanity
        metrics = mgr.get_metrics()
        assert metrics["total_requests"] >= 1
        assert "providers" in metrics and "ollama" in metrics["providers"]
    finally:
        await mgr.close()