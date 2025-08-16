import json
import types
import pytest

# Under test
import neuroca.integration.adapters.ollama as ollama_module
from neuroca.integration.adapters.ollama import OllamaAdapter
from neuroca.integration.models import LLMResponse, TokenUsage, ResponseType


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
    """Mimics aiohttp.ClientSession with post/get methods used by OllamaAdapter."""
    def __init__(self, *args, **kwargs):
        self.closed = False
        # Store last requests for debug assertions if needed
        self._last_post = None
        self._last_get = None

    async def close(self):
        self.closed = True

    def post(self, url: str, json: dict):
        self._last_post = (url, json)
        # Route based on endpoint
        if url.endswith("/api/generate"):
            # Minimal successful generation payload
            resp = FakeResponse(
                200,
                {
                    "response": "Hi from Ollama",
                    "eval_count": 5,
                    "prompt_eval_count": 3,
                    "total_duration": 1234,
                    "model": json.get("model", "gemma3:4b"),
                },
            )
            return _RespCM(resp)
        if url.endswith("/api/embeddings"):
            resp = FakeResponse(200, {"embedding": [0.1, 0.2, 0.3, 0.4]})
            return _RespCM(resp)
        # Default: not found
        return _RespCM(FakeResponse(404, {"error": "not found"}))

    def get(self, url: str):
        self._last_get = (url,)
        # Models listing
        if url.endswith("/api/tags"):
            resp = FakeResponse(200, {"models": [{"name": "gemma3:4b"}, {"name": "mistral"}]})
            return _RespCM(resp)
        return _RespCM(FakeResponse(404, {"error": "not found"}))


@pytest.mark.asyncio
async def test_generate_text_success(monkeypatch):
    """Adapter.generate should return models.LLMResponse with expected content/metadata."""
    # Patch ClientSession creation to our fake
    monkeypatch.setattr(ollama_module.aiohttp, "ClientSession", FakeSession)

    adapter = OllamaAdapter(
        {
            "base_url": "http://localhost:11434",
            "default_model": "gemma3:4b",
            "request_timeout": 30,
            "max_retries": 1,
        }
    )

    resp: LLMResponse = await adapter.generate("Hello")
    assert isinstance(resp, LLMResponse)
    assert resp.content == "Hi from Ollama"
    assert resp.model == "gemma3:4b"
    assert resp.provider == "ollama"
    assert isinstance(resp.usage, TokenUsage)
    assert resp.metadata.get("adapter") == "ollama"


@pytest.mark.asyncio
async def test_generate_chat_formats_messages(monkeypatch):
    """Adapter.generate_chat should format messages into prompt and return a response."""
    monkeypatch.setattr(ollama_module.aiohttp, "ClientSession", FakeSession)
    adapter = OllamaAdapter({"base_url": "http://localhost:11434", "default_model": "gemma3:4b"})

    messages = [
        {"role": "system", "content": "You are helpful."},
        {"role": "user", "content": "Say hi."},
    ]
    resp: LLMResponse = await adapter.generate_chat(messages)
    assert isinstance(resp, LLMResponse)
    assert resp.content == "Hi from Ollama"
    assert resp.model == "gemma3:4b"
    assert resp.provider == "ollama"


@pytest.mark.asyncio
async def test_generate_embeddings_success(monkeypatch):
    """Adapter.generate_embedding should return ResponseType.EMBEDDING and embedding vector(s)."""
    monkeypatch.setattr(ollama_module.aiohttp, "ClientSession", FakeSession)
    adapter = OllamaAdapter({"base_url": "http://localhost:11434", "default_model": "gemma3:4b"})

    # Single text
    resp_single: LLMResponse = await adapter.generate_embedding("embed this")
    assert isinstance(resp_single, LLMResponse)
    assert resp_single.response_type == ResponseType.EMBEDDING
    assert isinstance(resp_single.content, list)
    assert all(isinstance(x, float) for x in resp_single.content)

    # Batch texts
    resp_batch: LLMResponse = await adapter.generate_embedding(["a", "b"])
    assert isinstance(resp_batch.content, list)
    assert all(isinstance(vec, list) for vec in resp_batch.content)


@pytest.mark.asyncio
async def test_fetch_available_models(monkeypatch):
    """Internal fetch method should cache a set of available models."""
    monkeypatch.setattr(ollama_module.aiohttp, "ClientSession", FakeSession)
    adapter = OllamaAdapter({"base_url": "http://localhost:11434", "default_model": "gemma3:4b"})

    # Access private method to populate cache (since get_available_models is cached/sync)
    models = await adapter._fetch_available_models()
    assert "gemma3:4b" in models
    assert "mistral" in models

    # get_available_models returns cached list
    cached = adapter.get_available_models()
    assert isinstance(cached, list)
    assert set(cached) == set(models)


@pytest.mark.asyncio
async def test_execute_via_request_path(monkeypatch):
    """Execute(request) path should route to generate using the provided model and params."""
    monkeypatch.setattr(ollama_module.aiohttp, "ClientSession", FakeSession)
    adapter = OllamaAdapter({"base_url": "http://localhost:11434", "default_model": "gemma3:4b"})

    # Build a models.LLMRequest
    from neuroca.integration.models import LLMRequest

    req = LLMRequest(
        provider="ollama",
        model="gemma3:4b",
        prompt="Hello via request",
        max_tokens=64,
        temperature=0.1,
        additional_params={"top_p": 0.9},
    )

    resp = await adapter.execute(req)
    assert isinstance(resp, LLMResponse)
    assert resp.content == "Hi from Ollama"
    assert resp.model == "gemma3:4b"
    assert resp.provider == "ollama"
