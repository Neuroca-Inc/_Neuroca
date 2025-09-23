# Neuroca Release Notes

## 1.0.0 – General Availability

Release date: 2025-09-22

Highlights

- **Async-first memory orchestration** – The `MemoryManager` and
  `MemoryRetrieval` flows were rebuilt to normalise tier selection, surface
  structured `MemoryRetrievalResult` payloads, and preserve metadata filters
  across working, episodic, and semantic memories.
- **Production vector search** – A dedicated `QdrantVectorBackend` now powers
  similarity queries with deterministic UUID handling, batched CRUD
  operations, and regression coverage for metadata-aware searches.
- **Knowledge graph relationships** – Long-term relationship management stores
  metadata bidirectionally, exposing create/update/delete helpers through the
  manager interface and validating behaviour against the in-memory and Neo4j
  backends.
- **Operational tooling** – The asynchronous benchmark harness and end-to-end
  validation suite exercise the full memory stack through the modern CLI
  bootstrapper, providing release-ready performance signals.
- **Documentation refresh** – README quick starts, backend guides, and API
  references were aligned with the async storage factory and new retrieval
  results so integrations reflect the shipped interfaces.

Breaking changes

- The legacy `MemoryRetrieval` stub now returns `MemoryRetrievalResult`
  instances and enforces tier validation. Custom callers should update any
  tuple-based unpacking logic accordingly.
- Storage backends integrate through `StorageBackendFactory.create_storage()`
  and the new `BackendType.QDRANT` option. Plugins that relied on
  `create_backend()` must migrate to the asynchronous factory APIs.
- Memory model compatibility shims moved into dedicated modules within
  `neuroca.memory.models`. Direct imports from `neuroca.memory.memory_items`
  should be updated to the re-exported package paths.

Upgrade notes

- Install optional extras (`pip install neuroca[vector,test]`) to pull in the
  Qdrant client library when enabling the production vector backend.
- Refresh tier configuration files to register the desired vector and knowledge
  graph backends. The docs include sample configuration blocks for local and
  managed deployments.
- Re-run the provided benchmarks or smoke tests after upgrading to validate the
  configured storage backends and confirm the async bootstrapper wiring.

## 1.0.0-rc1 – Release Candidate

Release date: 2025-09-19 (candidate)

Highlights

- Memory manager stabilization: clean demo run with one search hit, no warnings.
- Audit/events readiness: event bus compatibility (BaseEvent), tags metadata normalized; tests green.
- Production configuration: added config/production.yaml; Docker defaults to prod (ENV/NCA_ENV).
- Observability: Prometheus metrics publisher integrated; disabled by default in demo.
- Security: Codacy CLI Trivy shows zero vulnerabilities for poetry.lock and requirements.txt after tightening constraints (httpx, aiohttp, transformers, requests, protobuf, starlette, torch, pydantic, scikit-learn, urllib3). LangChain moved to optional extra.

Breaking changes (planned for 1.0.0)

- LangChain integration is optional by default; install with extras: `pip install .[integrations]`.
- Torch minimum version raised on supported Python versions.

Upgrade notes

- Review any custom constraints; align to new minimums.
- If using LangChain adapters, enable extras and validate workflows.

RC validation plan

- Soak test with a coding agent for several days under realistic load (chat sessions, memory churn, consolidation/decay active) and monitor metrics/events.
- Exercise CLI backup/restore in both SQLite and Postgres modes and validate recovery.
- Run full integration and end-to-end suites; fix any regressions before cutting 1.0.0.

## 0.1.0b1 – Beta Preview

**Release date:** 2025-09-16

The 0.1.0b1 beta refresh delivers the first cohesive release of the unified
Neuroca memory system. Highlights include:

- ✅ **Unified memory manager** – A single async-first `MemoryManager` powers
  all tiers while preserving the legacy compatibility layer for synchronous
  integrations.
- ✅ **Vector search integration** – Tier construction now provisions vector
  backends through `StorageBackendFactory`, enabling out-of-the-box similarity
  queries and long-term knowledge consolidation.
- ✅ **Async cognitive control** – The decision maker, planner, and
  metacognitive monitor operate against the async manager, sharing utilities
  for deterministic option scoring and plan generation.
- ✅ **Expanded regression coverage** – New unit and integration suites verify
  vector-backed search, tier maintenance, API routes, and compatibility shims
  across the package surface.
- ✅ **Developer experience upgrades** – Smoke-tested demo scripts, restored
  async test infrastructure, and vendored `pytest_asyncio` support ensure the
  full test suite executes reliably from source checkouts.

### Installation Notes

- Install production dependencies with `pip install neuroca`.
- For development and testing, install optional extras:
  - `pip install neuroca[dev,test]`
  - or via Poetry: `poetry install --with dev,test`

### Upgrade Guidance

- Regenerate configuration files if they reference the deprecated
  `neuroca.core.memory` module; the tiered manager is now exported from
  `neuroca.memory.manager`.
- Update cognitive-control extensions to use the async helper utilities in
  `neuroca.core.cognitive_control._async_utils`.
- Refresh local caches for vector indexes before running the maintenance
  workflow tests (`tests/integration/memory/test_maintenance_workflow.py`).

For historical releases and future updates, see the documentation portal at
<https://docs.neuroca.dev/>.
