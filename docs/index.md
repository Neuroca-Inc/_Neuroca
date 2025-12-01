<div align="center"><h1>NeuroCognitive Architecture (NCA)</h1></div>

Welcome to the official documentation for the NeuroCognitive Architecture (NCA) - a biologically-inspired cognitive framework designed to give Large Language Models (LLMs) **persistent, dynamic, and human-like memory**.

## Beyond Retrieval - Enabling Automatic Memory

NeuroCognitive Architecture (NCA) represents a fundamental shift away from common techniques like Retrieval-Augmented Generation (RAG), GraphRAG, PathRAG, and similar approaches. While those methods enhance LLMs by using external tools to **retrieve** information from vector databases or knowledge graphs at query time to augment a limited context window, **NCA enables the LLM itself to genuinely remember...** and not just remember, but remember persistently.

Instead of relying on external lookups, NCA integrates a **dynamic, multi-tiered internal memory system** inspired by human cognition. Information is processed, consolidated, prioritized, and can decay over time based on relevance and interaction frequency, managed by background cognitive processes.

In practice, the current implementation provides:

* A **three-tier memory system** (Short-Term / Working, Medium-Term / Episodic, Long-Term / Semantic) backed by configurable storage backends.
* Automatic promotion, consolidation, and decay logic inside the memory manager.
* An LLM integration layer that can transparently invoke the memory system when configured (for example via [`llm.query_llm`](src/neuroca/api/routes/llm.py:175)).

This allows an LLM equipped with NCA to:

* **Organically recall context:** Access relevant past interactions, learned facts, user preferences, and evolving goals without explicit retrieval calls from the *agent*.
* **Learn and adapt:** Evolve its effective knowledge over time based on stored interactions and consolidation behaviour.
* **Maintain coherence:** Push beyond fixed context windows by using memory tiers and summarization instead of raw history truncation alone.

Some higher-level cognitive and health features described in the wider docs are **partially implemented or experimental**; where that is the case, the corresponding documents should be read as design intent rather than a strict API contract.

## Key Features (Current Implementation)

* **Three-Tiered Memory System**
  * Short-Term / Working memory with capacity / TTL-style constraints.
  * Medium-Term / Episodic memory for recent interactions and session context.
  * Long-Term / Semantic memory for consolidated knowledge and durable facts.

* **Tiered Memory Manager**
  * Centralized `MemoryManager` orchestration over all tiers and backends.
  * Support for in-memory and SQLite-style backends out-of-the-box.
  * Search surfaces that combine semantic similarity with metadata filters.

* **LLM Integration Layer**
  * Provider-agnostic integration via an `LLMIntegrationManager`.
  * HTTP LLM endpoint ([`/api/llm/query`](api/endpoints.md)) that can enable memory context per request.
  * Optional streaming endpoint for token-by-token output.

* **Developer-Focused Demos**
  * Working sandbox client ([`sandbox/working_nca_client.py`](sandbox/working_nca_client.py:1)) that exercises the tiered memory system directly.
  * Benchmarks and tests under `tests/` and `benchmarks/` that validate memory behaviour and performance.

## Planned and Experimental Components

The following areas are present in the architecture and some code paths, but are still evolving and should be treated as **experimental**:

* **Cognitive Control Mechanisms**
  * Attention, planning, and metacognition components.
  * Executive functions for goal-directed behaviour.

* **Health Dynamics**
  * Health models and dynamics managers.
  * Health-aware modulation of responses.

* **Production / SRE Layer**
  * Kubernetes deployment patterns and auto-scaling strategies.
  * Advanced monitoring and alerting integrations.
  * Detailed incident runbooks and long-running soak-test procedures.

Each experimental area is documented in more detail in the architecture and operations sections, with indication of what is implemented today versus planned.

## Quick Navigation

### User Documentation

* [Integration](user/integration.md) — Integrating NCA with existing systems and autonomous agents.

### Technical Documentation

* [Architecture Overview](architecture/components.md) — System components and interactions.
* [API Reference](api/endpoints.md) — LLM, memory, health, metrics, and system/admin endpoints.
* [Memory Systems](architecture/decisions/adr-001-memory-tiers.md) — Memory tier architecture decisions.
* [Health System](architecture/decisions/adr-002-health-system.md) — Health dynamics design and status.

### Developer Documentation

* [Development Environment](development/environment.md) — Setting up the development environment.
* [Contributing Guidelines](development/contributing.md) — How to contribute.
* [Coding Standards](development/standards.md) — Code style and practices.
* [Workflow](development/workflow.md) — Development workflow.

### Operations Documentation

* [Deployment](operations/deployment.md) — Deployment procedures and options.
* [Monitoring](operations/monitoring.md) — Monitoring and observability.
* [Incident Response](operations/runbooks/incident-response.md) — Handling incidents.
* [Backup and Restore](operations/runbooks/backup-restore.md) — Data protection procedures.

## Project Status

Neuroca / NCA is currently in an **active alpha** state:

* ✅ Core tiered memory system and manager.
* ✅ Working HTTP LLM endpoint and integration manager.
* ✅ Docker / Docker Compose paths for local and production-like runs.
* ✅ Extensive unit, integration, and performance tests around memory tiers.
* ⚠️ Cognitive control and health systems are present but evolving.
* ⚠️ Some documentation and diagrams describe roadmap features not yet fully implemented.

The public API surface (especially around cognitive/health components) may change as the architecture is refined. The memory and LLM integration paths documented under `api/` and `architecture/` are the most stable integration points.

## License

This project is licensed under the MIT License - see the [LICENSE](../LICENSE) file for details.

## Acknowledgments

The NeuroCognitive Architecture draws inspiration from neuroscience research on human cognition and memory systems. We acknowledge the contributions of researchers in cognitive science, neuroscience, and artificial intelligence that have made this work possible.
