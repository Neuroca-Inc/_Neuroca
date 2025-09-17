# Cognitive Control & Health Lifecycle

The Neuroca cognitive-control subsystem coordinates planning, execution, and
continuous monitoring on top of the unified async memory manager. This guide
summarizes how the major components collaborate after the recent refactor.

## Decision Maker

- **Entrypoint:** `neuroca.core.cognitive_control.decision_maker.DecisionMaker`
- **Responsibilities:**
  - Collect health snapshots and strategic goals.
  - Use `_async_utils.ensure_memory_manager` to normalize tier access.
  - Evaluate candidate options concurrently via `evaluate_options_async`.
  - Persist working-memory traces for downstream planners when necessary.
- **Memory interactions:** Searches STM/MTM/LTM through
  `AsyncMemoryManager.search_memories` using the unified `MemoryTier` enum.
- **Outcomes:** Returns the best-ranked option or defers to the planner when no
  confident choice exists.

## Planner

- **Entrypoint:** `neuroca.core.cognitive_control.planner.Planner`
- **Responsibilities:**
  - Generate multi-step plans with `generate_plan` leveraging semantic memory
    lookups to ground each step.
  - Recover from execution failures with `replan`, pruning invalid steps and
    reinforcing successful ones.
  - Store episodic summaries of completed plans for future decisions.
- **Memory interactions:**
  - Reads semantic knowledge via `search_memories`.
  - Persists episodic snapshots with `add_memory` for post-execution analysis.

## Metacognitive Monitor

- **Entrypoint:** `neuroca.core.cognitive_control.metacognition.MetacognitiveMonitor`
- **Responsibilities:**
  - Observe planner/decision-maker outcomes and compute confidence scores.
  - Detect anomalies or degraded health metrics and trigger corrective
    strategies.
  - Emit structured telemetry through the health monitor for observability.
- **Memory interactions:**
  - Records diagnostic events in the semantic tier.
  - Pulls historical decisions from episodic memory to detect drift.

## Health Monitoring

- **Entrypoint:** `neuroca.core.memory.health.MemoryHealthMonitor`
- **Responsibilities:**
  - Aggregate tier metrics (consolidation counts, decay events, failure rates).
  - Surface alerts back to cognitive-control modules for adaptive decision
    making.
  - Provide structured metrics payloads consumed by observability pipelines.

## Extending the Lifecycle

1. **Inject custom evaluators** by subclassing `DecisionMaker` and overriding
   `_score_option` while reusing `_async_utils` for memory access.
2. **Add planner strategies** by composing new generators that call
   `Planner.generate_plan` with domain-specific heuristics.
3. **Publish custom health events** through `MemoryHealthMonitor.execute` to
   enrich the telemetry captured by the metacognitive monitor.

For detailed API signatures, see the source modules referenced above or the
`tests/unit/cognitive_control` suite for executable examples.
