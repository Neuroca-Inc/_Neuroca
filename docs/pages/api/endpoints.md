# Neuroca HTTP API Surface (v1 Draft)

> Status: This document freezes the current HTTP surface for the first design-partner / monetized deployments. Any future breaking change must be introduced via a new version (for example `/api/v2/...`).

## Conventions

- **Base prefix:** All routes below assume the default FastAPI app includes the routers under the `/api` prefix as configured in [`__init__.py`](src/neuroca/api/routes/__init__.py).
- **Authentication:** This document uses "auth: required" to mean the route depends on an authenticated user object (for example via API key or session middleware), and "auth: admin" to mean only administrative callers are allowed.
- **Status codes:** Only non-2xx codes explicitly raised in the handlers are listed; generic framework / validation errors are omitted for brevity.
- **Rate limiting:** No hard rate limits are currently enforced in code. If a reverse proxy or API gateway adds limits, they must be documented separately.

---

## 1. Memory API v1

- **Router:** [`memory_v1.py`](src/neuroca/api/routes/memory_v1.py)
- **Base path:** `/api/v1/memory`
- **Auth:** required (all endpoints depend on an authenticated user).

### 1.1 POST /api/v1/memory — Create memory

- **Handler:** [`create_memory()`](src/neuroca/api/routes/memory_v1.py:189)
- **Request body:** JSON object describing the memory to create (tier, content, metadata, tags, etc.; see OpenAPI schema for exact fields).
- **Response body:** JSON memory record containing `id`, `user_id`, `tier`, `content`, and `metadata`.
- **Success:** `201 Created` with body as above.
- **Errors:**
  - `401 Unauthorized` if authentication is not configured or fails (see fallback in [`memory_v1.py`](src/neuroca/api/routes/memory_v1.py)).
  - `409 Conflict` when the target memory tier is full (raised from tier capacity checks).
  - `500 Internal Server Error` for storage failures or unexpected exceptions.

### 1.2 GET /api/v1/memory/{memory_id} — Get single memory

- **Handler:** [`get_memory()`](src/neuroca/api/routes/memory_v1.py:228)
- **Path parameters:**
  - `memory_id` (UUID) — identifier of the memory to retrieve.
- **Response body:** Memory record JSON as in 1.1.
- **Success:** `200 OK`.
- **Errors:**
  - `401 Unauthorized` if auth fails.
  - `403 Forbidden` if the authenticated user is not the owner and is not an admin (enforced by access checks).
  - `404 Not Found` if the memory does not exist.
  - `500 Internal Server Error` for unexpected errors.

### 1.3 GET /api/v1/memory — List memories

- **Handler:** [`list_memories()`](src/neuroca/api/routes/memory_v1.py:267)
- **Query parameters:**
  - `tier` (optional string) — filter by memory tier key (for example `stm`, `mtm`, `ltm`).
  - `query` (optional string) — full-text search query over content and/or metadata.
  - `tags` (optional repeated string) — filter by tags.
  - `limit` (int, default 50, max 100) — page size.
  - `offset` (int, default 0) — offset for pagination.
- **Response body:** JSON array of memory records visible to the current user (owner or admin).
- **Success:** `200 OK`.
- **Errors:**
  - `401 Unauthorized` if auth fails.
  - `500 Internal Server Error` if listing fails unexpectedly.

### 1.4 PUT /api/v1/memory/{memory_id} — Update memory

- **Handler:** [`update_memory()`](src/neuroca/api/routes/memory_v1.py:301)
- **Path parameters:**
  - `memory_id` (UUID) — identifier of the memory to update.
- **Request body:** JSON object describing the partial update (content and/or metadata).
- **Response body:** Updated memory record JSON.
- **Success:** `200 OK`.
- **Errors:**
  - `401 Unauthorized` if auth fails.
  - `403 Forbidden` if current user is not owner/admin.
  - `404 Not Found` if the memory does not exist.
  - `500 Internal Server Error` for storage or unexpected errors.

### 1.5 DELETE /api/v1/memory/{memory_id} — Delete memory

- **Handler:** [`delete_memory()`](src/neuroca/api/routes/memory_v1.py:356)
- **Path parameters:**
  - `memory_id` (UUID) — identifier of the memory to delete.
- **Success:** `204 No Content`.
- **Errors:**
  - `401 Unauthorized` if auth fails.
  - `403 Forbidden` if current user is not owner/admin.
  - `404 Not Found` if the memory does not exist.
  - `500 Internal Server Error` for unexpected errors.

### 1.6 POST /api/v1/memory/transfer — Transfer memory between tiers

- **Handler:** [`transfer_memory()`](src/neuroca/api/routes/memory_v1.py:397)
- **Request body:** JSON object with `memory_id` (UUID as string) and `target_tier` (tier key).
- **Response body:** Updated memory record JSON in the new tier.
- **Success:** `200 OK`.
- **Errors:**
  - `401 Unauthorized` if auth fails.
  - `403 Forbidden` if user lacks access to the memory.
  - `404 Not Found` if the memory does not exist.
  - `409 Conflict` or `500 Internal Server Error` for tier or storage errors.

---

## 2. LLM API

- **Router:** [`llm.py`](src/neuroca/api/routes/llm.py)
- **Base path:** `/api/llm`
- **Auth:** none enforced in this router; recommended to protect via gateway or future auth middleware.

### 2.1 POST /api/llm/query — Single-shot LLM query

- **Handler:** [`query_llm()`](src/neuroca/api/routes/llm.py:175)
- **Request body:**
  - `prompt` (string, required) — user prompt.
  - `provider` (string, default `"ollama"`).
  - `model` (string, default `"gemma3:4b"`).
  - `max_tokens` (int, default 128).
  - `temperature` (float, default 0.2).
  - `memory_context` (bool, default false) — if true and in-process memory is available, augments prompt with retrieved memories.
  - `health_aware` (bool, default false) — if true and health subsystem is available, includes health context.
  - `goal_directed` (bool, default false) — if true and goal manager is available, enables goal-directed behavior.
  - `additional_context` (object, optional) — arbitrary key/value metadata (for example `session_id`, `system_directive`, UI hints).
  - `style` (string, default `"detailed"`) — response style hint (for example `"concise"`, `"detailed"`, `"step_by_step"`).
  - `verbosity` (int, default 3, range 0–10).
- **Response body:** JSON object with fields:
  - `content` (string) — model response text.
  - `provider` (string) — final provider used.
  - `model` (string) — final model used.
  - `usage` (optional object) — token usage if available (`prompt_tokens`, `completion_tokens`, `total_tokens`).
  - `elapsed_time` (optional float, seconds).
  - `metadata` (optional object) — provider-specific metadata.
- **Success:** `200 OK`.
- **Errors:**
  - `502 Bad Gateway` if the provider call fails (for example local Ollama daemon not running).
  - `500 Internal Server Error` for unexpected errors creating or cleaning up managers.

### 2.2 GET /api/llm/stream — SSE streaming

- **Handler:** [`stream_llm()`](src/neuroca/api/routes/llm.py:321)
- **Query parameters:** similar to 2.1 (`prompt`, `provider`, `model`, `max_tokens`, `temperature`, `memory_context`, `health_aware`, `goal_directed`, `style`, `verbosity`, `session_id`, `system_directive`).
- **Behavior:**
  - For `provider="ollama"`, streams tokens directly from the local Ollama `/api/generate` endpoint when reachable.
  - Emits an initial `meta` event containing memory hit information when memory integration is enabled.
  - Emits `token` events for each token chunk and a final `end` event with elapsed time.
  - For non-Ollama providers or failures, falls back to single-shot behavior and pseudo-streams the final content.
- **Success:** `200 OK` with `text/event-stream` body.
- **Errors:**
  - `4xx/5xx` codes propagated from the upstream provider when using Ollama.
  - `500 Internal Server Error` or `502 Bad Gateway` on unexpected failures or upstream unavailability.

---

## 3. Health & Readiness API

- **Router:** [`health.py`](src/neuroca/api/routes/health.py)
- **Base path:** `/api/health`

### 3.1 GET /api/health — Basic health check

- **Handler:** [`health_check()`](src/neuroca/api/routes/health.py:146)
- **Auth:** none (intended for load balancers and simple probes).
- **Response body:** `{"status": "healthy"}` on success.
- **Behavior:**
  - Returns `503 Service Unavailable` while the app is still starting up.
  - Returns `503 Service Unavailable` if the database connection check fails.
- **Status codes:** `200 OK`, `503 Service Unavailable`.

### 3.2 GET /api/health/detailed — Detailed health

- **Handler:** [`detailed_health_check()`](src/neuroca/api/routes/health.py:202)
- **Auth:**
  - In production: requires a valid API key (rejected with `401 Unauthorized` otherwise).
  - In non-production: no auth required.
- **Response body:** rich JSON structure (see `DetailedHealthResponse` schema) including:
  - Overall status (healthy, degraded, unhealthy, optimal).
  - Version, environment, `uptime_seconds`, `timestamp`.
  - Per-component detailed health data including parameters and recent events.
  - System resource utilization and host information.
- **Status codes:**
  - `200 OK` when overall status is not critical or impaired.
  - `503 Service Unavailable` when any component is in a critical or impaired state or when an unexpected error occurs.
  - `401 Unauthorized` when required auth is missing (production).

### 3.3 GET /api/health/readiness — Readiness probe

- **Handler:** [`readiness_probe()`](src/neuroca/api/routes/health.py:367)
- **Auth:** none.
- **Behavior:**
  - Fails with `503 Service Unavailable` until application startup is complete.
  - Fails with `503 Service Unavailable` if the database is not ready.
  - Implicitly validates memory subsystem initialization via dependency injection.
- **Response body:** `{"status": "ready"}` on success.
- **Status codes:** `200 OK`, `503 Service Unavailable`.

### 3.4 POST /api/health/components/{component_id}/force_state — Force component state

- **Handler:** [`force_component_state()`](src/neuroca/api/routes/health.py:436)
- **Auth:**
  - In production: requires API key.
- **Request body:** JSON object with `state` field specifying the new health state enum value.
- **Status codes:** `200 OK`, `401 Unauthorized`, `404 Not Found`, `500 Internal Server Error`.

### 3.5 POST /api/health/components/{component_id}/adjust_parameter — Adjust health parameter

- **Handler:** [`adjust_component_parameter()`](src/neuroca/api/routes/health.py:482)
- **Auth:**
  - In production: requires API key.
- **Request body:** JSON object with `parameter_name` and `new_value` fields.
- **Status codes:** `200 OK`, `401 Unauthorized`, `404 Not Found`, `422 Unprocessable Entity`, `500 Internal Server Error`.

---

## 4. Metrics API

- **Router:** [`metrics.py`](src/neuroca/api/routes/metrics.py)
- **Base path:** `/api/metrics`
- **Auth:** all routes require an authenticated user; some require admin permissions.

### 4.1 GET /api/metrics/health — System health metrics

- **Handler:** [`get_system_health()`](src/neuroca/api/routes/metrics.py:98)
- **Auth:** authenticated user.
- **Response body:** aggregated system health metrics (CPU, memory, disk, network, component health, error rates).
- **Status codes:** `200 OK`, `500 Internal Server Error`.

### 4.2 GET /api/metrics/memory — Memory system metrics

- **Handler:** [`get_memory_metrics()`](src/neuroca/api/routes/metrics.py:127)
- **Auth:** authenticated user.
- **Query parameters:** `tier` (optional string to filter by memory tier).
- **Response body:** per-tier and overall memory-system metrics (usage, access patterns, latency, hit/miss rates, health indicators).
- **Status codes:** `200 OK`, `400 Bad Request` for invalid tier, `500 Internal Server Error`.

### 4.3 GET /api/metrics/performance — Performance metrics

- **Handler:** [`get_performance_metrics()`](src/neuroca/api/routes/metrics.py:163)
- **Auth:** authenticated user.
- **Query parameters:** `component` (optional), `period` (defaults to `"1h"`).
- **Response body:** performance metrics such as response times, throughput, error rates, and resource usage for the requested period.
- **Status codes:** `200 OK`, `400 Bad Request` for invalid parameters, `500 Internal Server Error`.

### 4.4 POST /api/metrics/custom — Submit single custom metric

- **Handler:** [`submit_metric()`](src/neuroca/api/routes/metrics.py:205)
- **Auth:** authenticated user.
- **Request body:** JSON metric payload with `name`, `value`, optional `timestamp`, and arbitrary label map.
- **Behavior:** metric is queued for asynchronous processing; the call does not wait for storage.
- **Status codes:** `201 Created`, `400 Bad Request` for validation errors, `500 Internal Server Error`.

### 4.5 POST /api/metrics/batch — Submit batch metrics

- **Handler:** [`submit_metrics_batch()`](src/neuroca/api/routes/metrics.py:253)
- **Auth:** authenticated user.
- **Request body:** JSON array of metric payloads as in 4.4.
- **Status codes:** `201 Created`, `400 Bad Request` when batch is empty, `500 Internal Server Error`.

### 4.6 POST /api/metrics/definitions — Register metric definition

- **Handler:** [`register_metric_definition()`](src/neuroca/api/routes/metrics.py:305)
- **Auth:** admin (requires admin-level permission).
- **Request body:** JSON metric-definition payload (name, description, type, unit, aggregation strategy, `retention_days`, allowed labels).
- **Response body:** registered metric definition.
- **Status codes:** `201 Created`, `400 Bad Request` for invalid definitions, `500 Internal Server Error`.

### 4.7 GET /api/metrics/definitions — List metric definitions

- **Handler:** [`list_metric_definitions()`](src/neuroca/api/routes/metrics.py:348)
- **Auth:** authenticated user (admin recommended).
- **Response body:** array of all metric definitions.
- **Status codes:** `200 OK`, `500 Internal Server Error`.

### 4.8 GET /api/metrics/definitions/{name} — Get single metric definition

- **Handler:** [`get_metric_definition()`](src/neuroca/api/routes/metrics.py:371)
- **Auth:** authenticated user.
- **Path parameters:** `name` (metric name).
- **Status codes:** `200 OK`, `404 Not Found` when metric is unknown, `500 Internal Server Error`.

### 4.9 DELETE /api/metrics/definitions/{name} — Delete metric definition

- **Handler:** [`delete_metric_definition()`](src/neuroca/api/routes/metrics.py:402)
- **Auth:** admin.
- **Path parameters:** `name` (metric name).
- **Status codes:** `204 No Content`, `404 Not Found`, `500 Internal Server Error`.

### 4.10 GET /api/metrics/data/{name} — Query time-series data

- **Handler:** [`get_metric_data()`](src/neuroca/api/routes/metrics.py:437)
- **Auth:** authenticated user.
- **Path parameters:** `name` (metric name).
- **Query parameters:** time range (`start_time`, `end_time`), `interval`, `aggregation`, `limit`, and optional `labels` filter.
- **Response body:** time-series data with timestamps, values, and aggregates.
- **Status codes:** `200 OK`, `404 Not Found`, `400 Bad Request` for invalid parameters, `500 Internal Server Error`.

### 4.11 GET /api/metrics/summary/{name} — Metric summary

- **Handler:** [`get_metric_summary()`](src/neuroca/api/routes/metrics.py:499)
- **Auth:** authenticated user.
- **Path parameters:** `name` (metric name).
- **Response body:** summary statistics for the metric over a default time window (min, max, avg, last, count, etc.).
- **Status codes:** `200 OK`, `404 Not Found`, `400 Bad Request`, `500 Internal Server Error`.

---

## 5. System / Admin API

- **Router:** [`system.py`](src/neuroca/api/routes/system.py)
- **Base path:** `/api/system`
- **Auth:** all routes require an authenticated admin user.

### 5.1 GET /api/system/info — System information

- **Handler:** [`get_system_info()`](src/neuroca/api/routes/system.py:110)
- **Auth:** admin.
- **Response body:** global information about the running deployment (version, environment, uptime, host, platform, Python version).
- **Status codes:** `200 OK`, `500 Internal Server Error`.

### 5.2 GET /api/system/health — System-wide health

- **Handler:** [`health_check()`](src/neuroca/api/routes/system.py:159)
- **Auth:** admin.
- **Query parameters:** `detailed` (bool, optional) — include per-component details.
- **Response body:** health status, timestamp, per-component statuses, and optional details structure.
- **Status codes:** `200 OK`, `500 Internal Server Error`.

### 5.3 GET /api/system/configuration — List configuration

- **Handler:** [`get_configuration()`](src/neuroca/api/routes/system.py:213)
- **Auth:** admin.
- **Query parameters:** `filter` (optional key prefix).
- **Response body:** array of configuration items (key, value, description, editable flag), with sensitive keys omitted.
- **Status codes:** `200 OK`, `500 Internal Server Error`.

### 5.4 PUT /api/system/configuration — Update configuration

- **Handler:** [`update_configuration()`](src/neuroca/api/routes/system.py:273)
- **Auth:** admin.
- **Request body:** JSON object with `key` and `value` fields for the setting to update.
- **Behavior:** rejects unknown or protected keys with appropriate error codes.
- **Status codes:** `200 OK` (wrapped as success response), `404 Not Found` for unknown keys, `403 Forbidden` for protected keys, `400 Bad Request` for failed updates, `500 Internal Server Error`.

### 5.5 GET /api/system/resources — Resource utilization

- **Handler:** [`get_resource_utilization()`](src/neuroca/api/routes/system.py:340)
- **Auth:** admin.
- **Response body:** CPU, memory, disk, and network usage snapshot in megabytes / gigabytes and percentages.
- **Status codes:** `200 OK`, `500 Internal Server Error`.

### 5.6 POST /api/system/maintenance — Toggle maintenance mode

- **Handler:** [`set_maintenance_mode()`](src/neuroca/api/routes/system.py:404)
- **Auth:** admin.
- **Request body:** JSON object with `enabled` (bool), optional `message`, and optional `estimated_duration_minutes`.
- **Behavior:** updates process-level maintenance flags and may trigger background maintenance operations when enabling.
- **Status codes:** `200 OK` (wrapped success), `500 Internal Server Error`.

### 5.7 POST /api/system/restart — Request system restart

- **Handler:** [`restart_system()`](src/neuroca/api/routes/system.py:468)
- **Auth:** admin.
- **Behavior:** schedules a controlled process restart as a background task; exact restart mechanism is implementation-specific.
- **Status codes:** `200 OK` (wrapped success), `500 Internal Server Error`.

---

## 6. Notes for API Surface Freeze

- This document reflects the behavior of the current Neuroca backend as implemented in the referenced route modules.
- For the monetization track, these endpoints and their request/response semantics are considered **frozen for v1** except for strictly additive changes (for example new optional fields or new endpoints).
- Any breaking change (removed fields, changed types, altered semantics) must be guarded behind a new versioned prefix (for example `/api/v2/...`) and documented separately.
- Future work (Tasks B–E) will extend this surface with authenticated multi-tenancy, metering, quotas, and operational policies but **must not** break the contracts documented here.

---

## 7. Operational Limits, SLAs, and Error Semantics (v1 Design-Partner Phase)

This section summarizes **current behavior and recommended operational envelopes** for the main endpoint groups. It is intentionally conservative and non-binding for the initial
design-partner phase. Formal customer SLAs will sit on top of, not inside, this document.

Unless otherwise noted:

- The backend does **not** enforce hard payload size limits beyond what is implied by individual field validations and query parameters.
- Global timeouts, connection limits, and rate limits are expected to be enforced by the deployment environment (for example reverse proxy, gateway, or orchestrator).
- Clients are expected to implement their own retry policies with exponential backoff for transient failures (5xx, network timeouts).

### 7.1 Memory API v1

**Scope:** `/api/v1/memory/*` routes implemented in [`memory_v1.py`](src/neuroca/api/routes/memory_v1.py:1).

#### Payload size and pagination

- **Request bodies:**
  - No explicit request-body size limit is enforced by the route handlers.
  - Practical limits are determined by:
    - Pydantic validation of the memory content and metadata models.
    - Any reverse proxy `client_max_body_size` (or equivalent) in front of the API.
  - **Recommendation for design partners:** keep individual `content` fields under ~32 KB of UTF‑8 text and total JSON bodies under ~256 KB per request to avoid pathological memory usage or serialization overhead in early deployments.

- **Listing and search pagination:**
  - `GET /api/v1/memory`:
    - `limit` has a **documented maximum** of `100`. Requests specifying a higher `limit` value are clamped or rejected according to handler validation.
    - `offset` is unbounded from the API perspective but should be kept reasonably small for latency and cost reasons.
  - **Recommendation:** treat `(limit=100, offset<=10_000)` as a safe upper bound for design-partner usage; larger offsets should be replaced with cursor‑style pagination in future versions.

#### Timeouts and retries

- The Memory API handlers do not define per-route timeouts; end‑to‑end timeouts are governed by:
  - Uvicorn / ASGI server configuration.
  - Database driver and connection‑pool timeouts in the configured backend.
- The service does **not** automatically retry failed storage operations on behalf of the caller.
  - Idempotent GET/DELETE requests may be retried by clients on network or generic 5xx failures.
  - Non‑idempotent POST/PUT requests should only be retried when the client can safely detect that the original operation failed without being applied.

#### Latency expectations (non‑binding)

- Typical behavior in a local Postgres or equivalent backing store under light load:
  - Single record reads (`GET /api/v1/memory/{id}`): **sub‑100 ms** end‑to‑end.
  - Short listings (`GET /api/v1/memory` with `limit ≤ 50`): typically **sub‑200 ms**.
- Under heavier load, slow storage, or very large datasets, latencies may increase. Production‑grade deployments should:
  - Monitor memory API latencies via the Metrics API.
  - Define their own SLOs (for example p95 < 250 ms for reads) before offering contractual SLAs.

#### Error semantics overview

In addition to the per‑route codes already documented above, Memory API v1 uses the following patterns:

- **Authentication / authorization:**
  - `401 Unauthorized` — no or invalid auth context.
  - `403 Forbidden` — authenticated but not owner/admin of the target memory.
- **Resource state and capacity:**
  - `404 Not Found` — missing memory resource.
  - `409 Conflict` — tier capacity or storage conflict (for example target tier full on transfer or create).
- **Server / storage failures:**
  - `500 Internal Server Error` — unexpected exceptions in the service layer or underlying storage.

Clients should treat 4xx responses as non‑retriable unless user input changes, and 5xx/transport failures as candidates for **bounded** retries.

---

### 7.2 LLM API

**Scope:** `/api/llm/*` routes implemented in [`llm.py`](src/neuroca/api/routes/llm.py:1).

#### Payload size and token limits

- **Prompt and parameters:**
  - `POST /api/llm/query` accepts free‑form `prompt` strings with no explicit size cap enforced by the route itself.
  - The **effective** limit is determined by:
    - The `max_tokens` parameter (default **128**).
    - The underlying provider’s model context window (for example the configured `model` in a local Ollama instance).
  - **Recommendation for design partners:**
    - Aim for prompts of **≤ 2–4 KB** of UTF‑8 text for low‑latency local models.
    - Keep `max_tokens` modest (≤ 256) for interactive usage unless benchmarks justify larger values.

- **Streaming (`GET /api/llm/stream`):**
  - Shares the same logical constraints as `query`, but responses are delivered incrementally as SSE events.
  - Upstream providers (for example Ollama) may enforce their own internal payload and token limits.

#### Timeouts and retries

- The LLM API delegates outbound calls to the integration layer in [`LLMIntegrationManager`](src/neuroca/integration/manager.py:1).
  - Timeouts are controlled by provider‑specific client configurations (for example HTTP client timeouts for Ollama or OpenAI) and the ASGI server/global config.
- The API does **not** automatically retry failed provider calls in a way that is visible as a single request to the caller:
  - On provider errors or unreachability:
    - `POST /api/llm/query` returns `502 Bad Gateway` or `500 Internal Server Error`.
    - `GET /api/llm/stream` terminates the SSE stream with a non‑2xx status and no further events.
- **Client guidance:**
  - Implement exponential‑backoff retries for `502`/`503`/`504` and network timeouts.
  - Avoid automatic retries on prompts that trigger provider‑side validation errors (4xx from upstream).

#### Latency expectations (non‑binding)

- Local LLMs (for example Ollama with `gemma3:4b`) on commodity hardware:
  - First token for streaming responses: typically **< 2–3 seconds** after request start under light load.
  - Full completion for short prompts and modest `max_tokens`: **a few seconds** end‑to‑end.
- Exact latency depends heavily on:
  - Model size and quantization.
  - Hardware (CPU vs GPU, memory bandwidth).
  - Concurrent load.
- For design‑partner deployments, target O(1–5s) response times for most interactive calls and monitor via custom latency metrics.

#### Error semantics overview

- `POST /api/llm/query`:
  - `502 Bad Gateway` — provider call failed or upstream (for example Ollama daemon) is unreachable.
  - `500 Internal Server Error` — unexpected errors constructing managers, integrating memory/health context, or handling the result.
- `GET /api/llm/stream`:
  - 4xx/5xx codes may be propagated from the upstream provider when streaming directly (for example Ollama).
  - `500` / `502` — internal adapter failures or upstream unavailability.

Clients should distinguish between:

- **Upstream/provider failures** (`502`, propagated 4xx/5xx) — often transient; retries may be appropriate.
- **Validation errors** (4xx from the Neuroca API itself, once added via future auth/tenancy work) — should be treated as non‑retriable until input is corrected.

---

### 7.3 Metrics API

**Scope:** `/api/metrics/*` routes implemented in [`metrics.py`](src/neuroca/api/routes/metrics.py:1).

#### Payload size and batch limits

- **Single custom metric (`POST /api/metrics/custom`):**
  - Expects a single metric payload (`name`, `value`, optional `timestamp`, labels).
  - No explicit per‑request size limit is enforced beyond sensible JSON object size; label maps and metadata should remain small.

- **Batch metrics (`POST /api/metrics/batch`):**
  - Accepts an array of metric payloads as per the single‑metric schema.
  - The handler validates that the batch is non‑empty (`400 Bad Request` on an empty list).
  - **Recommendation for design partners:**
    - Limit batches to **≤ 1_000** metric samples or **≤ 256 KB** of JSON per request to avoid blocking the event loop or overwhelming the downstream metrics store.
    - Prefer streaming or periodic batches over very large, spiky uploads.

#### Timeouts and retries

- Metrics routes typically perform light validation and then:
  - Query an in‑process metrics service for reads (`/health`, `/memory`, `/performance`, `/data`, `/summary`).
  - Queue or forward metric writes for asynchronous processing on `POST` endpoints.
- There are no explicit per‑route timeouts; end‑to‑end timeouts are driven by:
  - ASGI server configuration.
  - Backend metrics store or queue timeouts.
- **Client guidance:**
  - Retry idempotent GETs and metric submissions on transient 5xx errors or network timeouts.
  - Ensure that client‑side batching and retry policies avoid unbounded growth in queued metrics.

#### Latency expectations (non‑binding)

- Metrics reads and writes are generally low‑latency operations:
  - Health/performance snapshots: **sub‑200 ms** typical under normal load.
  - Time‑series queries (`/data/{name}`, `/summary/{name}`): depend on underlying store and time‑window/aggregation; expect **sub‑second** responses for small windows and index‑backed metrics.
- For high‑cardinality metrics or long historical windows, production deployments should:
  - Benchmark specific queries.
  - Establish SLOs and, if necessary, materialized views or pre‑aggregation.

#### Error semantics overview

- **Read endpoints (`/health`, `/memory`, `/performance`, `/definitions`, `/data`, `/summary`):**
  - `400 Bad Request` — invalid query parameters (for example, malformed time window or unknown tier).
  - `404 Not Found` — unknown metric name or definition.
  - `500 Internal Server Error` — unexpected failures in metrics service or data store.

- **Write endpoints (`/custom`, `/batch`, `/definitions`):**
  - `400 Bad Request` — invalid metric payloads or empty batches.
  - `201 Created` — accepted for processing; durable storage may still be asynchronous.
  - `500 Internal Server Error` — internal validation/storage errors.

As future work introduces per‑tenant quotas and billing (Tasks C1–C3), additional error codes such as `429 Too Many Requests` or domain‑specific 4xx payloads will be added. Those must be documented here as **additive**, non‑breaking changes.
