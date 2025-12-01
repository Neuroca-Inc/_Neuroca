# Neuroca HTTP API Examples (v1)

This document provides practical, **current** examples for using the Neuroca HTTP API surface as exposed by the FastAPI application. The examples here are aligned with the routes described in `endpoints.md` and the actual implementations in the `src/neuroca/api/routes/` package.

> All URLs below assume a local development server running at `http://127.0.0.1:8000` with the Neuroca routers mounted under the `/api` prefix. For example, `POST /v1/memory` means `POST http://127.0.0.1:8000/api/v1/memory`.

## 1. Authentication and Environment

In the current default development configuration:

- No API keys or OAuth flows are enforced by the routers themselves.
- Memory routes expect a logical user context but fall back to a demo user when explicit auth is not configured.
- LLM, health, metrics, and system routes can be protected by your reverse proxy or future auth middleware.

For production or shared deployments you **must** place the API behind an authentication layer (for example, an API gateway that injects a `user_id` or `X-API-Key` header). Tasks B1–B3 in the monetization track will formalize this model; for now, the examples below run against an unauthenticated local instance.

### 1.1 Starting the API locally

From the repository root, with a Python virtual environment activated and dependencies installed:

```bash
uvicorn neuroca.api.main:app --host 127.0.0.1 --port 8000 --reload
```

Once running, the interactive OpenAPI docs are available at:

- `http://127.0.0.1:8000/docs` (Swagger UI)
- `http://127.0.0.1:8000/redoc` (ReDoc), if enabled

All HTTP examples below use `curl` and Python's `requests` library.

## 2. Memory API v1 Examples

The versioned memory API is mounted under `/api/v1/memory` and implemented in the `memory_v1` router. It exposes CRUD and listing operations over a unified memory record model.

### 2.1 Create a memory — `POST /api/v1/memory`

**curl**

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/memory" \
  -H "Content-Type: application/json" \
  -d '{
    "tier": "stm",
    "content": "The meeting is scheduled for 3 PM tomorrow.",
    "metadata": {
      "source": "calendar",
      "category": "appointment"
    }
  }'
```

**Python**

```python
import requests

base_url = "http://127.0.0.1:8000/api"

response = requests.post(
    f"{base_url}/v1/memory",
    json={
        "tier": "stm",
        "content": "The meeting is scheduled for 3 PM tomorrow.",
        "metadata": {
            "source": "calendar",
            "category": "appointment",
        },
    },
)
response.raise_for_status()
memory = response.json()
print("Created memory:", memory["id"], "tier:", memory.get("tier"))
```

A successful response returns a JSON memory record with an `id`, the resolved `user_id`, the selected `tier`, and any stored metadata. Capacity or validation failures are returned with appropriate HTTP status codes (see the endpoint reference).

### 2.2 List memories — `GET /api/v1/memory`

To list memories visible to the current user:

```bash
curl "http://127.0.0.1:8000/api/v1/memory?tier=stm&limit=10"
```

```python
import requests

base_url = "http://127.0.0.1:8000/api"

response = requests.get(
    f"{base_url}/v1/memory",
    params={"tier": "stm", "limit": 10},
)
response.raise_for_status()
memories = response.json()
print("Returned", len(memories), "memory records")
```

### 2.3 Retrieve a single memory — `GET /api/v1/memory/{memory_id}`

```python
import requests

base_url = "http://127.0.0.1:8000/api"
memory_id = "YOUR_MEMORY_ID"

response = requests.get(f"{base_url}/v1/memory/{memory_id}")
if response.status_code == 404:
    print("Memory not found")
else:
    response.raise_for_status()
    print(response.json())
```

## 3. LLM API Examples

The LLM API is mounted under `/api/llm` and is optimized for local-first providers such as Ollama. By default, the API uses the provider and model configured in the application settings (see the LLM route docs).

### 3.1 Single-shot query — `POST /api/llm/query`

```python
import requests

base_url = "http://127.0.0.1:8000/api"

response = requests.post(
    f"{base_url}/llm/query",
    json={
        "prompt": "What is the capital of France?",
        "provider": "ollama",
        "model": "gemma3:4b",
        "max_tokens": 128,
        "temperature": 0.2,
        "verbosity": 3,
    },
)
response.raise_for_status()
data = response.json()
print("Model response:")
print(data["content"])
```

### 3.2 Streaming query (SSE) — `POST /api/llm/stream`

The streaming endpoint returns an HTTP Server-Sent Events (SSE) stream. The example below uses the `sseclient-py` package, but any SSE-capable client library will work.

```python
import requests
from sseclient import SSEClient  # pip install sseclient-py

base_url = "http://127.0.0.1:8000/api"

# Start the stream
response = requests.post(
    f"{base_url}/llm/stream",
    json={
        "prompt": "Stream a short story about a curious robot.",
        "provider": "ollama",
        "model": "gemma3:4b",
        "max_tokens": 128,
    },
    stream=True,
)

response.raise_for_status()

client = SSEClient(response)
for event in client.events():
    if event.event == "token":
        print(event.data, end="", flush=True)
    elif event.event == "end":
        break
```

## 4. Health, Metrics, and System Examples

### 4.1 Basic health and readiness

```bash
curl "http://127.0.0.1:8000/api/health/live"
curl "http://127.0.0.1:8000/api/health/ready"
```

Many deployments also expose a detailed health endpoint (for example `/api/health/detailed`) that includes per-component health dynamics and recent events. See the health routes section in the endpoint reference for the exact paths available in your build.

### 4.2 Querying metrics

Assuming metrics are enabled and at least one metric definition has been registered:

```bash
# List metric definitions
curl "http://127.0.0.1:8000/api/metrics/definitions"

# Fetch timeseries data for a specific metric (for example, llm_requests_total)
curl "http://127.0.0.1:8000/api/metrics/data/llm_requests_total"
```

### 4.3 System information

```bash
curl "http://127.0.0.1:8000/api/system/info"
```

Responses from the system routes include version, uptime, and configuration metadata useful for operators. Some system endpoints are intended for administrators only; protect them appropriately at the infrastructure layer.

## 5. Error Handling

The API uses standard HTTP status codes and structured JSON error responses. A typical error might look like:

```json
{
  "detail": "Memory not found"
}
```

When using `requests`, always call `raise_for_status()` to surface non‑2xx responses, and then inspect `response.json()` for additional details.

## 6. Conclusion

These examples demonstrate the core HTTP flows for the current Neuroca API surface: creating and querying memories, sending LLM requests (single‑shot and streaming), and inspecting health, metrics, and system status.

For more detailed information about specific endpoints, parameters, and response formats, refer to the HTTP API surface documentation and the generated OpenAPI schema:

- `docs/pages/api/endpoints.md`
- The `/docs` and `/openapi.json` endpoints exposed by the running FastAPI application.

For support and early‑access discussions, use the same contact channels documented in the main project README.