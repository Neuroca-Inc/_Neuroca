# Memory Subsystem Failure Recovery Runbook

This runbook outlines the recommended operator actions when the memory subsystem encounters
faults. It references metrics, events, and tooling introduced during the readiness work so
SREs can recover safely without risking data loss.

## 1. Consolidation failures

**Symptoms**

- `memory_consolidation_failures_total` increments rapidly or Prometheus alert
  `MemoryMaintenanceConsolidationFailureBurst` fires.
- Maintenance events report `ConsolidationOutcomeEvent` with `status="error"`.

**Recovery steps**

1. Inspect recent `MemoryConsolidated` audit events to confirm which tier transition failed.
2. Query the maintenance log (`tests/integration/memory/test_maintenance_workflow.py` mirrors the
   orchestration flow) to ensure the in-flight guard completed rollback.
3. Re-run the maintenance cycle using `MemoryManager.run_manual_maintenance_cycle()`; the
   transactional pipeline re-attempts any cached candidates with clean staging.
4. If the vector backend is implicated, execute `VectorIndexMaintenance.check_index_integrity()`
   to verify embeddings; follow up with `.reindex()` for affected namespaces.
5. Once successful, clear the alert and annotate the incident with the recovered promotion IDs.

## 2. Maintenance backlog growth

**Symptoms**

- `memory_maintenance_backlog_age_seconds` gauge drifts upward beyond the defined Grafana
  threshold.
- Adaptive retry delays in maintenance logs increase past baseline values.

**Recovery steps**

1. Confirm resource limits have not been exceeded by calling the
   `ResourceLimitWatchdog.debug_snapshot()` helper via the CLI shell.
2. Trigger a manual maintenance cycle; if backlog age continues rising, temporarily raise
   `maintenance.consolidation_batch_size` in configuration to let the tier pressure adapter
   promote larger batches.
3. Monitor `memory_consolidation_latency_seconds` histogram to ensure throughput improves.
4. After backlog stabilizes, revert temporary configuration and document the changes in the runbook
   log.

## 3. Vector index drift

**Symptoms**

- Quality analyzer reports elevated drift scores in the maintenance summary payload.
- Vector search regression tests or smoke checks return degraded recall.

**Recovery steps**

1. Execute `VectorIndexMaintenance.check_index_integrity()` for the impacted collection. Review the
   missing payloads and dimensional mismatches emitted by the helper.
2. Invoke `EmbeddingModelSwapCoordinator.plan_swap()` to verify whether a model transition is in
   progress; abort if compatibility checks fail.
3. Run `.reindex()` with the recommended batch size and monitor the emitted
   `MemoryMaintenanceConsolidation` events for completion.
4. After reindexing, execute a targeted semantic search smoke test to validate recall before closing
   the incident.

## 4. Sanitization or RBAC regressions

**Symptoms**

- API clients receive `400` errors citing prompt-injection or scope violations.
- Audit logs show repeated `MemorySanitizationRejected` entries for the same tenant.

**Recovery steps**

1. Examine the rejection payload in the audit log; sensitive fields are redacted but the reason code
   is retained for troubleshooting.
2. Use the optional `force=True` flag on maintenance CLI commands only after verifying the payload
   is safe; otherwise advise the calling team to adjust input data.
3. Validate RBAC scopes using the stored metadata inspector (see tuning guide) to confirm ownership
   tags are correct.

## 5. Graceful shutdown validation

**Scenario**: Prior to infrastructure maintenance, ensure no promotions are lost.

1. Call `MemoryManager.initiate_shutdown(wait=True)` to set the shared shutdown event.
2. Observe maintenance logs; the orchestrator waits for in-flight consolidations via
   `ConsolidationInFlightGuard.wait_for_all()`.
3. Once the shutdown completes, run a smoke retrieval to confirm persisted memories remain
   accessible.

## References

- Metrics definitions: `src/neuroca/memory/manager/metrics.py`.
- Maintenance events: `src/neuroca/memory/manager/events.py` and
  `src/neuroca/memory/manager/audit.py`.
- Vector tooling: `src/neuroca/memory/backends/vector/components/integrity.py` and
  `src/neuroca/memory/backends/vector/components/model_swap.py`.
