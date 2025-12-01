# NeuroCognitive Architecture (NCA) Integration Guide

This document describes how to integrate existing applications and autonomous agents with the current Neuroca codebase (NCA 1.0.0). It reflects the **actual FastAPI routes and Python components** in this repository, not the older hosted-SaaS design.

If you previously saw references to `https://api.neuroca.dev/v1/...` or a separate `neuroca-sdk` package, treat those as historical; the authoritative integration surface is the code in:

- HTTP LLM endpoint: [`llm.query_llm`](src/neuroca/api/routes/llm.py:175)
- Streaming LLM endpoint: [`llm.stream_llm`](src/neuroca/api/routes/llm.py:321)
- Memory system entrypoint (Python): [`MemoryManager`](sandbox/working_nca_client.py:61)

---

## 1. Integration Modes (High Level)

NCA supports two primary ways to integrate with your systems:

1. **LLM Proxy Mode (recommended for agents)**
   - You treat Neuroca as “the LLM”.
   - Your agent sends chat-style prompts to the HTTP LLM endpoint.
   - NCA internally manages STM/MTM/LTM tiers, consolidation, decay, and retrieval.
   - This matches the README promise: automatic background memory; no explicit memory API calls from the agent.

2. **In-Process Memory Mode (advanced / Python-only)**
   - You embed the memory manager directly in your Python process using the same components as the demos.
   - You call methods such as `add_memory` / `search_memories` on [`MemoryManager`](sandbox/working_nca_client.py:61).
   - Use this when you are building custom cognitive pipelines or running NCA entirely in-process.

The rest of this document focuses on **LLM Proxy Mode**, because that is how you plug NCA into an existing autonomous coding agent without rewriting the agent’s logic.

---

## 2. Prerequisites and Deployment

Before integrating, make sure you can run the Neuroca API locally or in your environment. The authoritative commands are in [`README.md`](README.md:128), but in summary:

### 2.1. Local venv (typical for development)

```bash
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e .  # from the Neuroca repository root

# Run the API
neuroca-api
# or
python -m uvicorn neuroca.api.main:app --host 127.0.0.1 --port 8000 --reload
```

The service will listen on `http://127.0.0.1:8000`. Health can be probed via:

```bash
curl -sf http://127.0.0.1:8000/api/health
```

### 2.2. Docker

See the “Production via Docker” and “Deploy with Docker Compose (Production‑ready quick start)” sections in [`README.md`](README.md:476) for current image and compose instructions.

---

## 3. LLM HTTP Endpoint (LLM Proxy Mode)

The central entrypoint for LLM proxy mode is the JSON endpoint implemented by [`llm.query_llm`](src/neuroca/api/routes/llm.py:175).

At runtime this route is mounted under whatever prefix the FastAPI app uses (commonly `/api`). For clarity this guide will assume `/api` as the prefix; if your app mounts routers differently, adjust the base path accordingly.

### 3.1. Request schema

The request body is defined by [`LLMQueryRequest`](src/neuroca/api/routes/llm.py:56):

```jsonc
{
  "prompt": "string, required",
  "provider": "ollama",               // default; can be another provider configured in LLMIntegrationManager
  "model": "gemma3:4b",               // default model name for the provider
  "max_tokens": 128,                  // 1–4096
  "temperature": 0.2,                 // 0.0–2.0

  "memory_context": false,            // enable automatic STM/MTM/LTM usage
  "health_aware": false,              // enable health-aware context (if HealthDynamicsManager is available)
  "goal_directed": false,             // enable goal-directed context (if GoalManager is available)

  "additional_context": {             // optional metadata; free-form dict
    "session_id": "agent-session-123",
    "system_directive": "optional extra system instructions",
    "...": "other keys your adapters may use"
  },

  "style": "detailed",                // "concise" | "detailed" | "step_by_step" (hint only)
  "verbosity": 3                      // 0–10; hint for answer length/detail
}
```

Key points:

- **Memory is feature-gated.** Setting `"memory_context": true` tells the route to initialize a full memory system via [`create_memory_system`](src/neuroca/api/routes/llm.py:40) and hand it to [`LLMIntegrationManager`](src/neuroca/api/routes/llm.py:248).
- **Session identity is metadata, not a query.** You typically pass a stable `session_id` in `additional_context` so that NCA scopes and accumulates memory per agent run or per user.
- **No explicit retrieval API is required.** The integration manager decides what to pull from STM/MTM/LTM for each turn when `memory_context` is enabled.

### 3.2. Basic HTTP example

Assuming the API is serving under `/api`:

```bash
curl -X POST http://127.0.0.1:8000/api/llm/query \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Summarize the last commit in a single sentence.",
    "provider": "ollama",
    "model": "gemma3:4b",
    "memory_context": true,
    "additional_context": {
      "session_id": "coding-agent-session-1"
    }
  }'
```

The response envelope is defined by [`LLMQueryResponse`](src/neuroca/api/routes/llm.py:91):

```jsonc
{
  "content": "string, the assistant response",
  "provider": "ollama",
  "model": "gemma3:4b",
  "usage": {
    "prompt_tokens": 123,
    "completion_tokens": 45,
    "total_tokens": 168
  },
  "elapsed_time": 0.42,
  "metadata": { "...": "provider-specific metadata" }
}
```

### 3.3. Python HTTP client example

To plug NCA into an existing Python autonomous agent, you typically implement a thin LLM client that talks to this endpoint instead of directly to OpenAI/Anthropic:

```python
import httpx
from typing import Any, Dict, List, Optional


class NeurocaLLMClient:
    """Thin HTTP client for the Neuroca LLM endpoint (LLM proxy mode)."""

    def __init__(self, base_url: str = "http://127.0.0.1:8000", api_prefix: str = "/api") -> None:
        self._base = base_url.rstrip("/")
        self._prefix = api_prefix.rstrip("/")

    def _url(self, path: str) -> str:
        return f"{self._base}{self._prefix}{path}"

    def chat(
        self,
        messages: List[Dict[str, Any]],
        *,
        session_id: Optional[str] = None,
        provider: str = "ollama",
        model: str = "gemma3:4b",
        memory_context: bool = True,
    ) -> Dict[str, Any]:
        # For now we flatten messages into a single prompt.
        # You can improve this by encoding roles and history in a template.
        joined = "\n".join(f"{m['role']}: {m['content']}" for m in messages)
        body: Dict[str, Any] = {
            "prompt": joined,
            "provider": provider,
            "model": model,
            "memory_context": memory_context,
            "additional_context": {},
        }
        if session_id is not None:
            body["additional_context"]["session_id"] = session_id

        resp = httpx.post(
            self._url("/llm/query"),
            json=body,
            timeout=60.0,
        )
        resp.raise_for_status()
        return resp.json()
```

You then inject this into your agent wherever it currently uses an LLM client. For example:

```python
class CodingAgent:
    def __init__(self, llm_client: NeurocaLLMClient) -> None:
        self._llm = llm_client

    def step(self, messages: list[dict], session_id: str) -> dict:
        return self._llm.chat(messages, session_id=session_id)
```

From the agent’s perspective, this still looks like “call chat with messages → get a response”; NCA’s tiered memory and consolidation now happen inside the Neuroca process.

---

## 4. Streaming LLM Output

If you want token-by-token streaming (for UIs or live logs), you can use the SSE endpoint implemented by [`llm.stream_llm`](src/neuroca/api/routes/llm.py:321).

This endpoint:

- Streams `{"type": "token", "content": "..."}` events as the model generates text.
- Optionally emits a first `{"type": "meta", "memory_hits": ..., "memories": [...]}` event to show memory usage when `memory_context=true`.
- Sends a final `{"type": "end", "elapsed": ...}` event when complete.

The exact URL will depend on how the router is mounted (typically `GET /api/llm/stream`). The query parameters correspond to the function signature in [`llm.stream_llm`](src/neuroca/api/routes/llm.py:321).

---

## 5. In-Process Memory Integration (Advanced)

For advanced Python use cases where you want direct control over the memory system without going through HTTP, you can use the same components as the working sandbox client [`WorkingNCAClient`](sandbox/working_nca_client.py:50).

Key facts from [`sandbox/working_nca_client.py`](sandbox/working_nca_client.py:1):

- Memory is initialized with [`MemoryManager`](sandbox/working_nca_client.py:61) and in-memory backends via `BackendType.MEMORY`.
- The client demonstrates:
  - `add_memory(...)` for storing interactions and knowledge.
  - `search_memories(...)` for retrieving relevant items.
  - A simple “cognitive pipeline” (`_retrieve_memories`, `_build_context`, `_generate_response`) built directly on top of the manager.

This mode is useful when:

- You are building a fully custom cognitive loop in Python.
- You want to run NCA entirely in-process without an HTTP boundary.
- You need to experiment with custom consolidation/decay policies.

However, for **plugging into an existing autonomous coding agent**, LLM Proxy Mode (Section 3) remains the recommended integration point.

---

## 6. Notes on Deprecated / Historical Surface Areas

Several older documentation artifacts and examples in this repository describe APIs that do **not** match the current implementation:

- Hosted endpoints at `https://api.neuroca.dev/v1/...`
- A separate `neuroca-sdk` package
- Endpoints like `/v1/cognitive/process`, `/v1/memory/store`, `/v1/memory/retrieve`
- A monolithic top-level `NeuroCognitiveArchitecture` object with rich sub-APIs (`nca.memory.working`, `nca.diagnostics`, etc.)

These represent **design direction and prior iterations**, not the current shipped interface. When in doubt, treat:

- The FastAPI routes under `src/neuroca/api/routes`
- The memory demos in `sandbox/`
- The GA entrypoints described in [`README.md`](README.md:128)

as the canonical, supported surface.

---

## 7. Recommended Next Steps

For a real integration with an autonomous coding agent today:

1. **Stand up Neuroca locally** using the commands in [`README.md`](README.md:128).
2. **Implement a thin LLM client** like the `NeurocaLLMClient` example above and point it at `/llm/query`.
3. **Enable `memory_context=true`** and pass a stable `session_id` for each long-running agent flow.
4. Optionally, **experiment with `WorkingNCAClient`** in [`sandbox/working_nca_client.py`](sandbox/working_nca_client.py:1) to understand the tiered memory behaviour in more detail.
5. When ready, document your exact agent wiring (LLM client, session id scheme, config) in your own repo so it’s reproducible.

This reflects the current implementation and is intended to be stable enough to monetize on as a “persistent memory backend for agents” product.