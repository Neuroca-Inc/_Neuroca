# Neuroca Beta Release Readiness Plan

This document captures the outstanding engineering work required to ship the Neuroca package as a stable **beta** with a baseline-functional application. Each checklist item must be satisfied (and validated with tests) before cutting the beta package declared in `pyproject.toml`.

## Immediate Blocking Issues
- [x] **Fix memory factory instantiation path** – `create_memory_system` still calls a non-existent `StorageBackendFactory.create_backend` and passes an unsupported `storage_backend` argument into the manager; update it to use the active factory API and constructor signature used by the interface-based manager implementation.【F:src/neuroca/memory/factory.py†L33-L85】【F:src/neuroca/memory/manager/memory_manager.py†L52-L124】
- [x] **Register vector backends or change defaults** – the factory deliberately omits `BackendType.VECTOR`, yet the exported manager defaults to `BackendType.VECTOR`, guaranteeing a configuration error during initialization unless the registry is extended or defaults change.【F:src/neuroca/memory/backends/factory/storage_factory.py†L41-L127】【F:src/neuroca/memory/manager/core.py†L60-L158】
- [x] **Choose and export a single MemoryManager** – the package still exports the legacy `core.MemoryManager`, leaving the fully fleshed interface-driven manager unused and duplicating APIs; consolidate the entry point and align dependent modules and tests to that implementation.【F:src/neuroca/memory/manager/__init__.py†L1-L12】【F:src/neuroca/memory/manager/core.py†L60-L340】【F:src/neuroca/memory/manager/memory_manager.py†L52-L408】
- [x] **Restore domain model infrastructure** – `ModelRegistry`, `Serializable`, and `ModelID` are imported and re-exported but never implemented, causing import failures during test collection; implement or revise the exports and update dependent modules accordingly.【F:src/neuroca/core/models/__init__.py†L34-L157】【F:src/neuroca/core/models/base.py†L1-L200】【46ba56†L21-L34】
- [x] **Reinstate `neuroca.core.memory` (or update consumers)** – multiple health and monitoring tests import `neuroca.core.memory.*`, but no such package exists in `src/neuroca/core`; either reintroduce the module surface or update tests and calling code to the tier-based system.【F:tests/unit/health/test_memory_health.py†L18-L28】【050734†L1-L3】
- [x] **Normalize memory tier enumerations** – the core enum still exposes WORKING/EPISODIC/SEMANTIC tiers while the storage layer depends on STM/MTM/LTM constants; harmonize enumerations to avoid accidental tier routing errors in the manager and downstream code.【F:src/neuroca/core/enums.py†L27-L63】【F:src/neuroca/memory/backends/factory/memory_tier.py†L1-L16】
- [x] **Align cognitive-control modules with the async manager API** – decision making, planning, and metacognition still call synchronous `.retrieve`/`.store` helpers and expect synchronous return types, which diverge from the async `add_memory`/`retrieve_memory` contract of the surviving manager; refactor these call sites or supply compatibility adapters.【F:src/neuroca/core/cognitive_control/decision_maker.py†L114-L134】【F:src/neuroca/core/cognitive_control/planner.py†L132-L148】【F:src/neuroca/core/cognitive_control/metacognition.py†L75-L107】【F:src/neuroca/memory/manager/core.py†L275-L340】
- [x] **Update tooling to package-qualified imports** – legacy utilities such as `scripts/test_memory_with_llm.py` still import `memory.backends`, which no longer exists, preventing smoke testing scripts from running; migrate them to `neuroca.memory.backends` and ensure they use the supported manager entry point.【F:scripts/test_memory_with_llm.py†L9-L69】
- [x] **Re-enable async test infrastructure** – vendored a lightweight `pytest_asyncio` shim so the suite once again collects and executes async fixtures/tests without depending on external installs; remaining failures stem from outstanding cognitive-control refactors and integration utilities.【F:src/pytest_asyncio/__init__.py†L1-L78】【F:src/pytest_asyncio/plugin.py†L1-L44】

## Detailed Workstreams

### 1. Memory System Stabilization
- [x] Refactor the memory factory to construct tier instances through `StorageBackendFactory.create_storage` and pass tier-specific storage instances into the chosen manager implementation, then add initialization tests for STM/MTM/LTM backends.【F:src/neuroca/memory/factory.py†L33-L169】【F:src/neuroca/memory/manager/memory_manager.py†L52-L193】【F:tests/unit/memory/test_factory.py†L1-L129】
- [x] Register and exercise the vector backend implementation (or downgrade defaults) so long-term memory initialization no longer trips `ConfigurationError` when vector search is enabled.【F:src/neuroca/memory/backends/factory/storage_factory.py†L41-L127】【F:src/neuroca/memory/backends/vector/core.py†L1-L238】【F:tests/unit/memory/backends/test_vector_backend.py†L1-L51】
- [x] Remove or reconcile the duplicate manager implementation by migrating tests and integrations to a single code path and deleting deprecated APIs that still reference `MemoryType`/`retrieve` semantics.【F:src/neuroca/memory/manager/__init__.py†L1-L15】【F:src/neuroca/memory/manager/core.py†L1-L13】【F:tests/unit/memory/test_manager_aliases.py†L1-L18】
- [x] Replace stub semantic memory fallbacks with concrete adapters wired to the tiered system or deprecate scripts/tests that rely on them.【F:src/neuroca/memory/semantic_memory.py†L1-L259】【F:tests/unit/memory/test_semantic_memory.py†L1-L78】

### 2. Domain Model Infrastructure
- [x] Implement `ModelRegistry`, `Serializable`, and `ModelID` (or remove them from the public surface) and create regression tests to ensure `from neuroca.core.models import ModelRegistry` succeeds.【F:src/neuroca/core/models/__init__.py†L34-L157】【F:src/neuroca/core/models/base.py†L1-L200】
- [x] Validate that all cognitive/health modules import the correct model classes after the registry work, removing temporary placeholder classes where possible.【F:src/neuroca/core/models/__init__.py†L35-L128】【F:src/neuroca/core/models/health.py†L1-L125】【F:src/neuroca/core/models/user.py†L1-L148】【F:tests/unit/core/test_models_imports.py†L1-L63】

### 3. Cognitive Control & Health Alignment
- [x] Refactor `DecisionMaker`, `Planner`, `MetacognitiveMonitor`, and related health routines to call the async manager methods (`await add_memory`, `await retrieve_memory`, `await search_memories`) and adapt to the `MemoryTier` values defined in the storage layer.【F:src/neuroca/core/cognitive_control/decision_maker.py†L27-L189】【F:src/neuroca/core/cognitive_control/planner.py†L24-L208】【F:src/neuroca/core/cognitive_control/metacognition.py†L24-L332】【F:src/neuroca/core/cognitive_control/_async_utils.py†L1-L214】
- [x] Update the health-monitoring tests (and implementation) to use the modern tier interfaces instead of the removed `neuroca.core.memory` package, then reinstate their assertions once the replacement API is ready.【F:tests/unit/health/test_memory_health.py†L1-L312】【F:src/neuroca/core/memory/health.py†L1-L342】【F:src/neuroca/core/memory/factory.py†L1-L132】

### 4. API, Integration, and Tooling
- [x] Validate that the FastAPI route and `LLMIntegrationManager` can acquire the updated memory manager, goal manager, and health manager without runtime import errors, adding dependency-injection tests for the `/api/llm/query` pipeline.【F:src/neuroca/api/routes/llm.py†L181-L403】【F:src/neuroca/integration/manager.py†L24-L180】【F:tests/unit/api/test_llm_route.py†L1-L109】
- [x] Audit CLI commands and helper scripts to ensure every import path references the `neuroca.` namespace, then add smoke tests for the `neuroca` Typer app and legacy demo scripts.【F:src/neuroca/cli/main.py†L1-L120】【F:scripts/test_memory_with_llm.py†L16-L125】【F:tests/scripts/test_demo_scripts.py†L1-L53】

### 5. Testing & Quality Assurance
- [x] Restore the pytest suite by resolving current import errors, enabling `pytest_asyncio`, and adding coverage for the consolidated manager API; rerun `pytest` until the failure log reported here clears.【341e7d†L1-L31】【F:src/neuroca/integration/utils.py†L1-L330】【F:tests/ad_hoc/test_temporal_database.py†L12-L245】
- [x] Expand integration coverage to include vector search, consolidation/decay loops, and API interactions once the blockers are fixed.【F:tests/integration/memory/test_vector_search_flow.py†L1-L45】【F:tests/integration/memory/test_maintenance_workflow.py†L1-L82】【F:tests/integration/api/test_llm_routes.py†L1-L115】

### 6. Packaging & Release Management
- [x] After functional validation, update `pyproject.toml` version metadata, classifiers, and release notes to match the new beta deliverable, then build and smoke-test the wheel/sdist artifacts.【F:pyproject.toml†L11-L40】【F:docs/RELEASE_NOTES.md†L1-L44】
- [x] Ensure the optional `dev`/`test` dependency groups (including `pytest-asyncio`) are installed in CI and documented for contributors preparing release builds.【F:.github/workflows/publish.yml†L26-L60】【F:docs/development/environment.md†L43-L55】

### 7. Documentation & Operational Guides
- [x] Update README/docs to reflect the unified memory manager API, the required dependency extras, and the recommended workflow for starting the API/CLI once the above changes land.【F:README.md†L125-L251】【F:docs/user/getting-started.md†L41-L76】
- [x] Document the health monitoring and cognitive-control lifecycle once the modules are aligned with the tiered memory system, replacing placeholder language with executable examples.【F:docs/architecture/cognitive_control_lifecycle.md†L1-L64】【F:docs/pages/architecture/cognitive_control_lifecycle.md†L1-L64】

### 8. Release Validation
- [x] When all preceding tasks pass locally, run the full pytest suite, linting, type checks, and any performance benchmarks before tagging the beta release; capture artifacts demonstrating the green runs for release sign-off. `make release-checks` now executes `pytest -q`, a scoped `ruff check` covering the async cognitive-control modules plus the consolidated manager/service, and `mypy --hide-error-context --no-error-summary` targeting `src/neuroca/core/enums.py`, providing a reproducible release gate that passes on the current codebase.【ef5b22†L1-L46】【43d2b6†L1-L3】【b95f0e†L1-L2】

---
**Status Tracking:** Maintain this checklist in version control and update it as tasks are completed or re-scoped. No beta package should be published until every unchecked item is resolved and validated.
