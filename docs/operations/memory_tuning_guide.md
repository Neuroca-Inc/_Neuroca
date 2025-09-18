# Memory Maintenance Tuning Guide

This guide provides practical levers for tuning the memory subsystem once metrics are
available. Each section references configuration keys exposed through the factory overrides or
`settings.memory` block.

## Observability prerequisites

Before tuning, ensure the following telemetry is flowing:

- Prometheus metrics from `MemoryMetricsPublisher` (`memory_consolidation_latency_seconds`,
  `memory_decay_total`, `memory_maintenance_backlog_age_seconds`, etc.).
- Maintenance and quality events emitted via `MaintenanceEventPublisher` and `MemoryAuditTrail`.
- Grafana dashboard `memory_maintenance.json` imported with alert rules from
  `infrastructure/monitoring/rules/memory_maintenance_alerts.yml`.

## Consolidation throughput

- **Batch sizing** – Adjust `maintenance.consolidation_batch_size` to increase the number of STM
  records promoted per cycle. Monitor backlog age to avoid overloading MTM/LTM.
- **Pressure adapter sensitivity** – Modify `capacity_pressure.window` and
  `capacity_pressure.threshold` fields to smooth spikes. Lower thresholds react faster to
  saturation but can cause oscillations.
- **Retry cadence** – Update `maintenance.retry_min_seconds` / `retry_max_seconds` to control how
  quickly the orchestrator re-attempts after failures.

## Decay behaviour

- **Half-life tuning** – Override `decay.passive_half_life_seconds` or
  `decay.reinforcement_half_life_seconds` per tier to accelerate or slow forgetting. Use the decay
  math reference to understand the impact on reinforcement energy.
- **Forgetting thresholds** – Raising `decay.forgetting_threshold` prunes more aggressively;
  pair with `decay.importance_weight` to keep high-importance memories longer.
- **Manual decay tools** – Use the maintenance CLI to trigger manual decay when backlog grows
  faster than automated pruning.

## Resource utilisation

- **Watchdog limits** – Configure `resource_limits.tiers.<tier>.max_items` and
  `.ingest_timeout_seconds` to cap load. Combine with the back-pressure setting described below to
  prevent overload.
- **Back-pressure** – Enable the manager’s optional queued ingestion mode (see `MemoryManager`
  constructor `ingest_queue_max`) when anticipating bursts. Monitor the
  `memory_ingest_rejected_total` metric to gauge drop rates.

## Quality and recall

- **Summarizer weighting** – Tune `summarizer.keyword_weight` and
  `summarizer.max_sentences` to balance brevity vs. fidelity; run summarization regression tests to
  validate changes.
- **Vector health** – Schedule periodic `VectorIndexMaintenance.check_index_integrity()` calls and
  configure alerts on the emitted drift metrics.
- **Embedding swaps** – When changing embedding models, use the
  `EmbeddingModelSwapCoordinator.plan_swap()`/`execute_swap()` workflow to re-embed in batches and
  avoid downtime.

## RBAC & sanitization

- **Scope enforcement** – Confirm `MemoryRetrievalScope` defaults align with tenancy needs; adjust
  scope builders in `MemoryService` when new ownership dimensions are introduced.
- **Sanitizer rules** – Extend `MemorySanitizer` keyword lists or regexes when new prompt-injection
  techniques emerge. Always add matching regression coverage in
  `tests/unit/memory/manager/test_sanitization.py`.

## Tooling quick reference

| Tool | Purpose |
| --- | --- |
| `MemoryManager.run_manual_maintenance_cycle()` | Triggers consolidation/decay on demand. |
| `MemoryManager.initiate_shutdown(wait=True)` | Drains maintenance safely before restarts. |
| `VectorIndexMaintenance.check_index_integrity()` | Surfaces missing payloads and drift. |
| `ResourceLimitWatchdog.debug_snapshot()` | Shows current tier utilisation vs. limits. |
| `memory_bench.py` performance harness | Re-measures latency/throughput after tuning. |

Document all tuning changes in the ops journal along with before/after metric snapshots to aid
future capacity planning.
