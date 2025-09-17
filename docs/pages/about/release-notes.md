# Release Notes

## Version 0.1.0b1 – Beta Preview

**Release date:** 2025-09-16

The 0.1.0b1 beta refresh delivers the first cohesive release of the unified
Neuroca memory system. Highlights include:

- **Unified memory manager** – A single async-first `MemoryManager` powers all
  tiers while preserving the legacy compatibility layer for synchronous
  integrations.
- **Vector search integration** – Tier construction provisions vector backends
  through `StorageBackendFactory`, enabling out-of-the-box similarity queries
  and long-term knowledge consolidation.
- **Async cognitive control** – The decision maker, planner, and metacognitive
  monitor operate against the async manager, sharing utilities for
  deterministic option scoring and plan generation.
- **Expanded regression coverage** – New unit and integration suites verify
  vector-backed search, tier maintenance, API routes, and compatibility shims
  across the package surface.
- **Developer experience upgrades** – Smoke-tested demo scripts, restored async
  test infrastructure, and vendored `pytest_asyncio` support ensure the full
  test suite executes reliably from source checkouts.

### Installation Notes

- Install production dependencies with:

  ```bash
  pip install neuroca
  ```

- For development and testing, install optional extras:

  ```bash
  pip install neuroca[dev,test]
  # or via Poetry
  poetry install --with dev,test
  ```

### Upgrade Guidance

- Regenerate configuration files if they reference the deprecated
  `neuroca.core.memory` module; the tiered manager is now exported from
  `neuroca.memory.manager`.
- Update cognitive-control extensions to use the async helper utilities in
  `neuroca.core.cognitive_control._async_utils`.
- Refresh local caches for vector indexes before running the maintenance
  workflow tests (`tests/integration/memory/test_maintenance_workflow.py`).

For historical releases and future updates, watch the Neuroca repository or the
documentation portal.
