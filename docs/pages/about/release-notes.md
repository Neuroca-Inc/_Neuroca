# Release Notes

## Version 1.0.0 – General Availability

**Release date:** 2025-09-22

### Highlights

- **Async-first memory orchestration** – Legacy retrieval now funnels through
  the asynchronous tiers, returning structured `MemoryRetrievalResult` objects
  that honour metadata filters across working, episodic, and semantic stores.
- **Production vector search** – `QdrantVectorBackend` ships with deterministic
  UUID handling, batched CRUD operations, and relationship-preserving payloads
  so similarity queries align with long-term memory metadata.
- **Knowledge graph relationships** – Bidirectional relationship metadata is
  persisted through both the in-memory and Neo4j backends, and is exposed via
  new manager-level create/update/delete helpers.
- **Operational tooling** – An asynchronous performance harness and refreshed
  end-to-end validation suite exercise the storage factory and CLI bootstrapper
  exactly as production deployments will.
- **Documentation refresh** – README quick starts, backend guides, and API
  references document the async storage factory options and retrieval payloads
  introduced during the final release hardening.

### Breaking Changes

- `MemoryRetrieval.search()` now returns `MemoryRetrievalResult` objects and
  enforces tier validation. Update any tuple-based unpacking logic to consume
  the named attributes on the new model.
- Storage backends must register through `StorageBackendFactory.create_storage()`
  and the new `BackendType.QDRANT` entry. Extensions calling
  `create_backend()` should migrate to the asynchronous helpers.
- Compatibility shims for legacy memory models live in dedicated modules under
  `neuroca.memory.models`. Adjust direct imports from `memory_items` to the new
  package exports.

### Upgrade Guidance

- Install optional extras (`pip install neuroca[vector,test]`) to include the
  Qdrant client when enabling the production vector backend.
- Refresh tier configuration files to register vector and knowledge-graph
  backends. The documentation includes reference YAML snippets for local and
  managed deployments.
- Run the bundled benchmark or smoke-test scripts to verify async storage
  bootstrapper wiring after upgrading.

## Version 1.0.0-rc1 – Release Candidate

**Release date:** 2025-09-19 (candidate)

- Memory manager stabilization delivered a clean demo run with one search hit.
- Audit/event integrations aligned on canonical event payloads and metadata
  handling, with unit coverage on the event bus contract.
- Production configuration defaults to the hardened profile and ships with
  Prometheus hooks disabled by default for demo environments.
- Dependency constraints were tightened following Codacy Trivy scans; install
  LangChain adapters via `pip install neuroca[integrations]` when required.

## Version 0.1.0b1 – Beta Preview

**Release date:** 2025-09-16

The beta refresh delivered the first cohesive release of the unified Neuroca
memory system with async memory management, vector search integration, async
cognitive control, expanded regression coverage, and restored developer
experience tooling. Installation and upgrade notes for 0.1.0b1 remain available
in the repository history.

For historical releases and future updates, watch the Neuroca repository or the
documentation portal.
