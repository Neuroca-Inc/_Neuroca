# Neuroca Beta Release Readiness Plan

This document captures the outstanding engineering work required to ship the Neuroca package as a stable **beta** with a baseline-functional application. Each checklist item must be satisfied (and validated with tests) before cutting the beta package declared in `pyproject.toml`.

## Immediate Blocking Issues
- [ ] **Fix memory factory instantiation path** – `create_memory_system` still calls a non-existent `StorageBackendFactory.create_backend` and passes an unsupported `storage_backend` argument into the manager; update it to use the active factory API and constructor signature used by the interface-based manager implementation.【F:src/neuroca/memory/factory.py†L33-L85】【F:src/neuroca/memory/manager/memory_manager.py†L52-L124】
- [ ] **Register vector backends or change defaults** – the factory deliberately omits `BackendType.VECTOR`, yet the exported manager defaults to `BackendType.VECTOR`, guaranteeing a configuration error during initialization unless the registry is extended or defaults change.【F:src/neuroca/memory/backends/factory/storage_factory.py†L41-L127】【F:src/neuroca/memory/manager/core.py†L60-L158】
- [ ] **Choose and export a single MemoryManager** – the package still exports the legacy `core.MemoryManager`, leaving the fully fleshed interface-driven manager unused and duplicating APIs; consolidate the entry point and align dependent modules and tests to that implementation.【F:src/neuroca/memory/manager/__init__.py†L1-L12】【F:src/neuroca/memory/manager/core.py†L60-L340】【F:src/neuroca/memory/manager/memory_manager.py†L52-L408】
- [ ] **Restore domain model infrastructure** – `ModelRegistry`, `Serializable`, and `ModelID` are imported and re-exported but never implemented, causing import failures during test collection; implement or revise the exports and update dependent modules accordingly.【F:src/neuroca/core/models/__init__.py†L34-L157】【F:src/neuroca/core/models/base.py†L1-L200】【46ba56†L21-L34】
- [ ] **Reinstate `neuroca.core.memory` (or update consumers)** – multiple health and monitoring tests import `neuroca.core.memory.*`, but no such package exists in `src/neuroca/core`; either reintroduce the module surface or update tests and calling code to the tier-based system.【F:tests/unit/health/test_memory_health.py†L18-L28】【050734†L1-L3】
- [ ] **Normalize memory tier enumerations** – the core enum still exposes WORKING/EPISODIC/SEMANTIC tiers while the storage layer depends on STM/MTM/LTM constants; harmonize enumerations to avoid accidental tier routing errors in the manager and downstream code.【F:src/neuroca/core/enums.py†L27-L63】【F:src/neuroca/memory/backends/factory/memory_tier.py†L1-L16】
- [ ] **Align cognitive-control modules with the async manager API** – decision making, planning, and metacognition still call synchronous `.retrieve`/`.store` helpers and expect synchronous return types, which diverge from the async `add_memory`/`retrieve_memory` contract of the surviving manager; refactor these call sites or supply compatibility adapters.【F:src/neuroca/core/cognitive_control/decision_maker.py†L114-L134】【F:src/neuroca/core/cognitive_control/planner.py†L132-L148】【F:src/neuroca/core/cognitive_control/metacognition.py†L75-L107】【F:src/neuroca/memory/manager/core.py†L275-L340】
- [ ] **Update tooling to package-qualified imports** – legacy utilities such as `scripts/test_memory_with_llm.py` still import `memory.backends`, which no longer exists, preventing smoke testing scripts from running; migrate them to `neuroca.memory.backends` and ensure they use the supported manager entry point.【F:scripts/test_memory_with_llm.py†L16-L61】
- [ ] **Re-enable async test infrastructure** – `pytest` currently fails during collection because `pytest_asyncio` is not installed and numerous imports are unresolved; once module gaps are closed, ensure the `dev`/`test` extras (or the CI environment) install `pytest-asyncio` so async fixtures execute correctly.【46ba56†L1-L79】【F:tests/integration/memory/test_memory_tier_integration.py†L8-L33】【F:pyproject.toml†L78-L104】

## Detailed Workstreams

### 1. Memory System Stabilization
- [ ] Refactor the memory factory to construct tier instances through `StorageBackendFactory.create_storage` and pass tier-specific storage instances into the chosen manager implementation, then add initialization tests for STM/MTM/LTM backends.【F:src/neuroca/memory/factory.py†L33-L125】【F:src/neuroca/memory/manager/memory_manager.py†L52-L193】
- [ ] Register and exercise the vector backend implementation (or downgrade defaults) so long-term memory initialization no longer trips `ConfigurationError` when vector search is enabled.【F:src/neuroca/memory/backends/factory/storage_factory.py†L41-L127】【F:src/neuroca/memory/backends/vector/core.py†L1-L120】
- [ ] Remove or reconcile the duplicate manager implementation by migrating tests and integrations to a single code path and deleting deprecated APIs that still reference `MemoryType`/`retrieve` semantics.【F:src/neuroca/memory/manager/__init__.py†L1-L12】【F:src/neuroca/memory/manager/core.py†L60-L340】
- [ ] Replace stub semantic memory fallbacks with concrete adapters wired to the tiered system or deprecate scripts/tests that rely on them.【F:src/neuroca/memory/semantic_memory.py†L1-L26】

### 2. Domain Model Infrastructure
- [ ] Implement `ModelRegistry`, `Serializable`, and `ModelID` (or remove them from the public surface) and create regression tests to ensure `from neuroca.core.models import ModelRegistry` succeeds.【F:src/neuroca/core/models/__init__.py†L34-L157】【F:src/neuroca/core/models/base.py†L1-L200】
- [ ] Validate that all cognitive/health modules import the correct model classes after the registry work, removing temporary placeholder classes where possible.【F:src/neuroca/core/models/__init__.py†L44-L114】

### 3. Cognitive Control & Health Alignment
- [ ] Refactor `DecisionMaker`, `Planner`, `MetacognitiveMonitor`, and related health routines to call the async manager methods (`await add_memory`, `await retrieve_memory`, `await search_memories`) and adapt to the `MemoryTier` values defined in the storage layer.【F:src/neuroca/core/cognitive_control/decision_maker.py†L114-L174】【F:src/neuroca/core/cognitive_control/planner.py†L132-L200】【F:src/neuroca/core/cognitive_control/metacognition.py†L75-L160】【F:src/neuroca/memory/backends/factory/memory_tier.py†L11-L16】
- [ ] Update the health-monitoring tests (and implementation) to use the modern tier interfaces instead of the removed `neuroca.core.memory` package, then reinstate their assertions once the replacement API is ready.【F:tests/unit/health/test_memory_health.py†L18-L156】

### 4. API, Integration, and Tooling
- [ ] Validate that the FastAPI route and `LLMIntegrationManager` can acquire the updated memory manager, goal manager, and health manager without runtime import errors, adding dependency-injection tests for the `/api/llm/query` pipeline.【F:src/neuroca/api/routes/llm.py†L32-L210】【F:src/neuroca/integration/manager.py†L24-L180】
- [ ] Audit CLI commands and helper scripts to ensure every import path references the `neuroca.` namespace, then add smoke tests for the `neuroca` Typer app and legacy demo scripts.【F:src/neuroca/cli/main.py†L1-L120】【F:scripts/test_memory_with_llm.py†L16-L125】

### 5. Testing & Quality Assurance
- [ ] Restore the pytest suite by resolving current import errors, enabling `pytest_asyncio`, and adding coverage for the consolidated manager API; rerun `pytest` until the failure log reported here clears.【46ba56†L1-L79】【F:tests/integration/memory/test_memory_tier_integration.py†L8-L40】
- [ ] Expand integration coverage to include vector search, consolidation/decay loops, and API interactions once the blockers are fixed.【F:src/neuroca/memory/manager/core.py†L200-L340】【F:src/neuroca/api/routes/llm.py†L200-L309】

### 6. Packaging & Release Management
- [ ] After functional validation, update `pyproject.toml` version metadata, classifiers, and release notes to match the new beta deliverable, then build and smoke-test the wheel/sdist artifacts.【F:pyproject.toml†L11-L75】
- [ ] Ensure the optional `dev`/`test` dependency groups (including `pytest-asyncio`) are installed in CI and documented for contributors preparing release builds.【F:pyproject.toml†L78-L104】

### 7. Documentation & Operational Guides
- [ ] Update README/docs to reflect the unified memory manager API, the required dependency extras, and the recommended workflow for starting the API/CLI once the above changes land.【F:README.md†L1-L120】【F:src/neuroca/cli/main.py†L1-L120】
- [ ] Document the health monitoring and cognitive-control lifecycle once the modules are aligned with the tiered memory system, replacing placeholder language with executable examples.【F:src/neuroca/core/cognitive_control/metacognition.py†L31-L160】【F:src/neuroca/core/cognitive_control/decision_maker.py†L14-L180】

### 8. Release Validation
- [ ] When all preceding tasks pass locally, run the full pytest suite, linting, type checks, and any performance benchmarks before tagging the beta release; capture artifacts demonstrating the green runs for release sign-off.【46ba56†L1-L79】【F:pyproject.toml†L78-L104】

---
**Status Tracking:** Maintain this checklist in version control and update it as tasks are completed or re-scoped. No beta package should be published until every unchecked item is resolved and validated.
