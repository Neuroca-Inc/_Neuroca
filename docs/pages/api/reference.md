# API Reference

This document provides detailed reference information for the NeuroCognitive Architecture (NCA) API.

## Core APIs

### Memory System

* [Memory Manager API](#memory-manager-api)
* [Memory Tier API](#memory-tier-api)
* [Memory Backend API](#memory-backend-api)
* [Memory Item API](#memory-item-api)
* [Memory Search API](#memory-search-api)

### Health System

* [Health Monitor API](#health-monitor-api)
* [Health Component API](#health-component-api)
* [Health Registry API](#health-registry-api)
* [Health Metrics API](#health-metrics-api)

### Cognitive Control System

* [Attention Manager API](#attention-manager-api)
* [Goal Manager API](#goal-manager-api)
* [Decision Maker API](#decision-maker-api)
* [Planner API](#planner-api)
* [Metacognition API](#metacognition-api)

## Attention Manager API

`AttentionManager` in `src/neuroca/core/cognitive_control/attention_manager.py` orchestrates cognitive focus across stimuli, goals, and plan steps. It tracks the current `AttentionFocus`, enforces capacity constraints derived from health dynamics, and exposes helpers like `allocate_attention()`, `shift_attention()`, and `filter_distraction()` to respond to contextual changes.

```python
from neuroca.core.cognitive_control.attention_manager import AttentionManager

attention = AttentionManager()
focus = attention.allocate_attention(
    [
        ("goal", "goal_release", 0.9),
        ("stimulus", "alert_signal", 0.6),
    ]
)
if focus:
    attention.shift_attention(focus.target_type, focus.target_id, urgency=0.5)
```

## Goal Manager API

`GoalManager` in `src/neuroca/core/cognitive_control/goal_manager.py` maintains goal hierarchies, activation states, and conflict-resolution heuristics. Use `add_goal()`, `activate_goal()`, `update_goal_status()`, and `get_active_goals()` to direct executive control while the manager records history and enforces biological-inspired resource limits.

```python
from neuroca.core.cognitive_control.goal_manager import GoalManager

goal_manager = GoalManager()
goal = goal_manager.add_goal("Publish 1.0 release", priority=2)
if goal:
    goal_manager.activate_goal(goal.id)
active_goals = goal_manager.get_active_goals()
```

## Decision Maker API

`DecisionMaker` in `src/neuroca/core/cognitive_control/decision_maker.py` evaluates `DecisionOption` candidates against active goals, health context, and episodic or semantic evidence. The asynchronous `choose_action()` helper normalizes health state, checks goal alignment, and can request subordinate plans when the selected option requires additional structure.

```python
from neuroca.core.cognitive_control.decision_maker import DecisionMaker, DecisionOption

decision_maker = DecisionMaker(goal_manager=goal_manager)
best_option = await decision_maker.choose_action(
    [
        DecisionOption(description="Ship release", action="deploy", estimated_utility=0.8, risk=0.2),
        DecisionOption(description="Delay release", action="pause", estimated_utility=0.5, risk=0.05),
    ],
    context={"current_goal_description": "Publish 1.0 release"},
)
```

## Planner API

`Planner` in `src/neuroca/core/cognitive_control/planner.py` synthesizes multi-step plans by blending semantic procedures with episodic recollections. Call `generate_plan()` with a goal description and optional context to receive a `Plan` composed of `PlanStep` objects that downstream managers can execute or adapt.

```python
from neuroca.core.cognitive_control.planner import Planner

planner = Planner(goal_manager=goal_manager)
plan = await planner.generate_plan("Publish 1.0 release", context={"health_state": "normal"})
if plan:
    for step in plan.steps:
        print(step.action, step.parameters)
```

## Metacognition API

`MetacognitiveMonitor` in `src/neuroca/core/cognitive_control/metacognition.py` aggregates telemetry from health, goals, and memory to support self-regulation. It logs anomalies into episodic memory, maintains rolling performance metrics, and offers `assess_current_state()` snapshots for dashboards and automated interventions.

```python
from neuroca.core.cognitive_control.metacognition import MetacognitiveMonitor

monitor = MetacognitiveMonitor(goal_manager=goal_manager)
await monitor.log_error({"type": "integration", "message": "Timeout", "component": "memory"})
state = await monitor.assess_current_state()
```

## Integration APIs

### LangChain Integration

* [Chain Integration API](#chain-integration-api)
* [Memory Integration API](#memory-integration-api)
* [Tool Integration API](#tool-integration-api)

### LLM Integration

* [LLM Connector API](#llm-connector-api)
* [Embedding API](#embedding-api)
* [Provider API](#provider-api)

## REST API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/memory/items` | GET | Retrieve memory items |
| `/api/v1/memory/items` | POST | Store a new memory item |
| `/api/v1/memory/items/{id}` | GET | Retrieve a specific memory item |
| `/api/v1/memory/items/{id}` | PUT | Update a memory item |
| `/api/v1/memory/items/{id}` | DELETE | Delete a memory item |
| `/api/v1/memory/search` | POST | Search memory |
| `/api/v1/health/status` | GET | Get system health status |
| `/api/v1/health/components` | GET | List health monitored components |
| `/api/v1/health/metrics` | GET | Get health metrics |
| `/api/v1/system/info` | GET | Get system information |

## GraphQL API

The GraphQL API provides a flexible interface for querying and mutating data in the NCA system. 

### Example Query

```graphql
query {
  memoryItems(tier: "working", limit: 5) {
    id
    content
    metadata {
      contentType
      createdAt
      importance
    }
    relationships {
      targetId
      relationshipType
      strength
    }
  }
  
  healthStatus {
    overallHealth
    components {
      name
      status
      metrics {
        name
        value
        unit
      }
    }
  }
}
```

### Example Mutation

```graphql
mutation {
  storeMemoryItem(
    input: {
      content: "This is a new memory item",
      tier: "working",
      metadata: {
        contentType: "text/plain",
        importance: 0.8
      }
    }
  ) {
    id
    status
  }
}
```

## Memory Manager API

The asynchronous `MemoryManager` orchestrates all tier operations, so callers must
initialize and tear down the manager inside an event loop. Each helper returns
structured `MemoryItem` models and enriches search results with tier metadata and
relevance scores.

```python
import asyncio
from neuroca.memory.manager import MemoryManager, MemoryTier


async def run_demo() -> None:
    manager = MemoryManager()
    await manager.initialize()

    await manager.add_memory(
        tier=MemoryTier.WORKING,
        content="Important information",
        metadata={"importance": 0.9, "content_type": "text/plain"},
    )

    results = await manager.search_memories(
        query="important",
        tiers=[MemoryTier.WORKING.value, MemoryTier.EPISODIC.value],
        limit=5,
    )

    for memory in results:
        print(memory["content"], memory.get("_relevance"))

    await manager.shutdown()


asyncio.run(run_demo())
```

For more detailed documentation, refer to the [Memory System Architecture](../architecture/diagrams/memory-system/index.md).

## Memory Tier API

The asynchronous `MemoryTierInterface` defined in `src/neuroca/memory/interfaces/memory_tier.py` standardizes lifecycle, CRUD, and query operations for the short-, medium-, and long-term tiers. Implementations such as `ShortTermMemoryTier`, `MediumTermMemoryTier`, and `LongTermMemoryTier` inherit from `BaseMemoryTier` to apply tier-specific policies for decay, promotion, cleanup, and telemetry while reusing the shared storage helpers.

- `initialize()` / `shutdown()` prepare tier resources and attached backends.
- `store()`, `retrieve()`, `update()`, `delete()`, and `exists()` provide async persistence semantics.
- `search()` applies tier-aware filters and returns `MemorySearchResults` objects enriched with relevance and tier metadata.

```python
from neuroca.memory.tiers.stm.core import ShortTermMemoryTier

tier = ShortTermMemoryTier()
await tier.initialize()

memory_id = await tier.store(
    {"text": "Reminder from onboarding"},
    metadata={"tags": {"topic": "demo"}},
)
results = await tier.search(query="Reminder", limit=5)

await tier.shutdown()
```

## Memory Backend API

`StorageBackendInterface` in `src/neuroca/memory/interfaces/storage_backend.py` encapsulates the low-level persistence contract for all tiers. Backends manage connection pools, atomic CRUD primitives, batched mutations, and vector-aware retrieval without any tier-specific assumptions. Use `StorageBackendFactory.create_storage()` to construct a backend for a particular tier and technology.

```python
from neuroca.memory.backends import BackendType, MemoryTier, StorageBackendFactory

backend = StorageBackendFactory.create_storage(
    tier=MemoryTier.STM,
    backend_type=BackendType.SQL,
    config={"database_url": "sqlite:///memory.db"},
)
await backend.initialize()
await backend.create("memory-id", {"content": {"text": "Cached response"}})
await backend.shutdown()
```

## Memory Item API

The Pydantic models in `src/neuroca/memory/models/memory_item.py` capture the schema for stored memories. `MemoryItem` aggregates `MemoryContent` and `MemoryMetadata`, exposing helpers like `mark_accessed()` and `calculate_activation()` so tiers and integrations share a consistent representation.

```python
from neuroca.memory.models.memory_item import MemoryContent, MemoryItem, MemoryMetadata

memory = MemoryItem(
    content=MemoryContent(text="Synced meeting notes"),
    metadata=MemoryMetadata(tags={"team": "research"}, importance=0.8),
)
memory.mark_accessed()
```

## Memory Search API

Structured query models live in `src/neuroca/memory/models/search.py`. `MemorySearchOptions` combines free-text queries, metadata filters, tier constraints, vector embeddings, sorting, and pagination controls. `MemorySearchResult` and `MemorySearchResults` wrap ranked results with similarity metadata, and the legacy `MemoryQuery` compatibility shim in `src/neuroca/memory/models/memory_query.py` preserves historical integrations.

```python
from neuroca.memory.models.memory_query import MemoryQuery
from neuroca.memory.models.search import MemorySearchOptions

options = MemorySearchOptions(
    query="vector databases",
    tiers=["ltm"],
    metadata_filters={"tags.category": "research"},
    limit=20,
    include_embedding=True,
)
compat_query = MemoryQuery(query=options.query, filters=options.metadata_filters)
```

## Health Monitor API

The Health Monitor API provides methods for monitoring and managing the health of the NCA system.

```python
from neuroca.core.health import HealthMonitor

# Create a health monitor
health_monitor = HealthMonitor()

# Get overall system health
health_status = health_monitor.get_status()

# Register a component for health monitoring
health_monitor.register_component(
    component_id="memory_manager",
    component_type="memory",
    thresholds={"memory_usage": 0.9, "error_rate": 0.01}
)

# Report a metric for a component
health_monitor.report_metric(
    component_id="memory_manager",
    metric_name="memory_usage",
    metric_value=0.75
)

# Get all metrics for a component
metrics = health_monitor.get_component_metrics("memory_manager")
```

For more detailed documentation, refer to the [Health System Architecture](../architecture/diagrams/health-system/index.md).

## Health Component API

Component health models in `src/neuroca/core/health/component.py` work with the orchestration utilities in `src/neuroca/core/health/monitor.py` to evaluate subsystem status. `ComponentStatus`, `ComponentHealthStatus`, and `ComponentHealthMetrics` describe runtime state, while `HealthCheck` and `HealthCheckResult` provide an extensible pattern for monitoring logic that can be scheduled by the `HealthMonitor`.

```python
from neuroca.core.health.monitor import HealthCheck, HealthCheckResult, HealthCheckStatus, HealthMonitor


class PingCheck(HealthCheck):
    """Minimal example that always reports a passing status."""

    def execute(self) -> HealthCheckResult:
        return self.create_result(HealthCheckStatus.PASSED, message="pong")


monitor = HealthMonitor()
monitor.register_check(PingCheck("ping", component_id="memory"))
results = monitor.run_all_checks()
```

## Health Registry API

`HealthRegistry` in `src/neuroca/core/health/registry.py` centralizes component registration and ties checks to the components they observe. Use it to look up registered components, enumerate their health checks, or detach monitors when subsystems are decommissioned.

```python
from neuroca.core.health.registry import get_health_registry

registry = get_health_registry()
registry.register_component("memory", component={"description": "Tiered memory system"})
registry.register_check(PingCheck("ping", component_id="memory"))
component_checks = registry.get_component_checks("memory")
```

## Health Metrics API

Metric definitions, metadata containers, and registries reside in `src/neuroca/core/health/metadata.py`. `HealthMetricDefinition` enforces value bounds and warning thresholds, `HealthMetadata` captures point-in-time metrics, and `MetadataRegistry` persists versioned histories for later analysis.

```python
from neuroca.core.health.metadata import HealthMetadata, HealthMetricDefinition, MetadataRegistry

throughput = HealthMetricDefinition(
    name="memory_throughput",
    description="Items processed per minute",
    unit="items/min",
    min_value=0.0,
    max_value=10_000.0,
    default_value=0.0,
    warning_threshold=7_500.0,
    critical_threshold=9_500.0,
)

metadata = HealthMetadata(
    component_id="memory",
    metrics={"memory_throughput": 6_200.0},
    category="memory",
    metric_definitions={"memory_throughput": throughput},
)

registry = MetadataRegistry()
registry.register(metadata)
```

## LangChain Integration API

The LangChain Integration API provides methods for integrating NCA with the LangChain framework.

```python
from neuroca.integration.langchain.chains import create_cognitive_chain
from neuroca.integration.langchain.memory import MemoryFactory
from neuroca.integration.langchain.tools import get_all_tools

# Create an NCA-powered chain
chain = create_cognitive_chain(
    llm=your_llm,
    memory_manager=your_memory_manager,
    health_monitor=your_health_monitor
)

# Use NCA memory with LangChain
memory = MemoryFactory.create_memory(memory_type="working")

# Get NCA tools for LangChain agents
tools = get_all_tools()

# Run the chain
result = chain.run("Process this information")
```

For more detailed documentation, refer to the [LangChain Integration Architecture](../architecture/diagrams/integration/langchain.md).

### Chain Integration API

`create_cognitive_chain()` in `src/neuroca/integration/langchain/chains.py` composes a LangChain `LLMChain` that enriches prompts with cognitive context, health awareness, and memory-backed tools. Provide the target LLM, memory manager, and health monitor to receive a chain pre-wired with NCA telemetry.

### Memory Integration API

`MemoryFactory` in `src/neuroca/integration/langchain/memory.py` offers helpers such as `create_memory()` for wiring STM, MTM, or LTM adapters into LangChain agents. It bridges LangChain's `BaseMemory` contracts with the asynchronous memory tiers used throughout the platform.

### Tool Integration API

`get_all_tools()` in `src/neuroca/integration/langchain/tools.py` returns a curated list of NCA-aware agent tools—including health diagnostics, memory inspection, and planning shortcuts—that can be registered with LangChain executors.

## LLM Integration API

The LLM integration layer in `src/neuroca/integration/manager.py` unifies outbound provider calls, prompt enhancement, and telemetry capture. Adapters in `src/neuroca/integration/adapters/` expose consistent generation, streaming, and embedding capabilities for OpenAI, Anthropic, Vertex AI, and Ollama runtimes.

### LLM Connector API

`LLMIntegrationManager` centralizes provider orchestration with asynchronous `query()` and streaming helpers that augment prompts with memory and goal context. Configure it with provider credentials and optional memory/health managers to enable health-aware retries, fallback providers, and cost tracking.

```python
from neuroca.integration.manager import LLMIntegrationManager

manager = LLMIntegrationManager(
    config={"providers": {"openai": {"api_key": "sk-..."}}, "default_provider": "openai"}
)
response = await manager.query("Summarize the latest consolidation metrics")
```

### Embedding API

Adapters expose `generate_embedding()` / `generate_embeddings()` methods for semantic search and similarity calculations. For example, the OpenAI and Ollama adapters implement embedding helpers that return standardized `LLMResponse` payloads enriched with provider metadata and token accounting.

### Provider API

Provider metadata models in `src/neuroca/integration/models.py`—including the `LLMProvider` enumeration, `ProviderConfig`, `LLMRequest`, and `LLMResponse` classes—define the payload contracts used across adapters and higher-level managers. Use them to serialize requests, record provider capabilities, and transport trace metadata between services.
