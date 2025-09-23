# Neuroca LLM Memory System Beta Readiness Checklist

This document provides a actionable, prioritized checklist for achieving beta readiness based on the current state: 53% test coverage, 100% passing tests (5 skipped), thousands of warnings from linting/deprecations, modular refactoring complete, and functional core (CRUD/retrieval/consolidation). Target: 95%+ coverage, zero warnings, validated soak/Docker. Estimated: 3-5 days.

Review the checklist and work through the items one at a time. Check items off as you work on them: [STARTED], [DONE], [RETRYING], [NOT STARTED]

This work is closed-beta readiness finalizing, do not put anything "out of scope" if it is listed as required for production release.

If tests fail because of any missing packages or installations, you need to install those and try to run the tests again. Same thing if you run into errors for missing packages.

## Core Functionality (100% Passing, Verify No Regressions)

- [ ] Run full test suite (pytest -v) to confirm 100% passes persist post-fixes
- [ ] Enable and pass 5 skipped tests (Redis/SQLite/Qdrant integrations; update legacy in test_tiered_storage.py lines 21-35)
- [ ] Validate end-to-end flows: memory lifecycle (create→consolidate→search; test_memory_flow_between_tiers lines 68-244)
- [ ] Confirm benchmarks: retrieval latency <100ms p95 (benchmarks.py lines 255-334), consolidation throughput >10 ops/sec (lines 364-491)
- [ ] Clean install succeeds on Python 3.10, 3.11, 3.12, 3.13 with Poetry >=2.2
  - [ ] poetry lock completes without solver issues
  - [ ] poetry install --with dev,test completes without errors
  - [ ] Pip-based alternative documented and tested (venv, pip install -e .)
- [ ] Heavy/optional deps are correctly gated
  - [ ] torch constrained off Py3.12/3.13 (no missing wheels)
  - [ ] Optional vector backends (faiss-cpu, qdrant-client) install and import OK
- [ ] matplotlib present for perf tests; non-GUI backend enforced (e.g., Agg)

## Testing Coverage (Current: 53%, Target: 95%)

- [ ] Expand unit tests for manager/cross-tier (test_plan phase 4 lines 238-242; aim +20% coverage)
- [ ] Add integration for backends/tiers (phase 2-3 lines 228-237; cover skips line 282)
- [ ] Implement mutation tests (line 15; use mutmut for quality)
- [ ] Run coverage report (pytest-cov); verify >=95% overall, >=90% critical paths (backends/manager)

## CI/CD and Quality Gates

- [ ] CI matrix covers Python 3.10–3.13
- [ ] Lint executes ruff on src/ and fails on errors
- [ ] Types execute mypy (target Python version consistent with CI); no new errors introduced
- [ ] Unit + integration tests run in CI; artifacts (coverage.xml) uploaded
- [ ] Coverage threshold enforced (proposed: >=85% or within 2% of baseline)
- [ ] Pre-commit hooks for fmt/lint active and documented

## Quality & Warnings (Thousands from Lint/Deprecations)

- [ ] Fix linting: ruff check --fix (409 violations; checklist lines 182-192)
- [ ] Format code: black --check (472 files; apply to suppress)
- [ ] Migrate Pydantic V1 validators to V2 (thread_safety line 52; search codebase for @validator)
- [ ] Update SQLAlchemy: replace declarative_base() (MovedIn20Warning; thread_safety line 52)
- [ ] Run mypy --strict; suppress/fix remaining warnings (hide-error-context for beta)
- [ ] Pre-commit: run --all-files; fix whitespace/endings (checklist lines 195-201)
- [ ] Reduce noisy warnings in tests (retain security-relevant warnings)
- [ ] Replace datetime.utcnow() with datetime.now(datetime.UTC)

## Operations & Performance

- [ ] Validate Docker: build/run compose (api/postgres/redis; checklist line 214)
- [ ] Execute soak test: 3-5 day LLM sessions (operations/soak-test.md; harness.py for anomalies)
- [ ] Benchmark full suite: run_benchmark_suite (benchmarks.py lines 936-987); compare reports (lines 990-1070)
- [ ] Health checks: integrate tier events with HealthMonitor (refactoring line 200)
- [ ] Prometheus exporter smoke test passes (/metrics)
- [ ] OpenTelemetry exports enabled/disable-able via config; sampling documented
- [ ] Structured logs carry request IDs / operation context
- [ ] Health endpoints and readiness/liveness checks verified

## Data and Migrations

- [ ] Alembic migrations validated: up/down on clean and populated DB
- [ ] Backup/restore path documented (neuroca_backup.sql samples)
- [ ] Data retention and PII handling documented (if applicable)

## Product/API Readiness

- [ ] Public API surface reviewed and frozen for closed beta (breaking changes noted)
- [ ] Error surfaces return structured, actionable messages
- [ ] Rate limits/backpressure documented and tested (where applicable)

## Documentation & Cleanup

- [ ] Unify redundancies: merge consolidation/decay (refactoring lines 101-104)
- [ ] Update docs: migration guides for facades (lines 350-385), test plan phases (lines 222-248)
- [ ] Final audit: no >500 LOC (AMOS), clean build (zero warnings post-fixes)
- [ ] Update environment docs to reflect Python 3.10–3.13 support
- [ ] Confirm examples and commands in README.md/docs/ work as-is
- [ ] API quickstart (FastAPI) verified: neuroca-api and uvicorn neuroca.api.main:app
- [ ] Minimal .env example updated and validated (Postgres, Redis)
- [ ] MkDocs page for this checklist linked in docs navigation (optional)

## Risk & Backout

- [ ] Known issues list captured with mitigations/workarounds
- [ ] Backout procedure documented (locking, revert, comms)
- [ ] Incident response contact and workflow (who/when/how)

## Rollout Plan & Feedback Loops

- [ ] Closed beta cohort defined and invited
- [ ] Onboarding doc/script prepared (setup, run, sample calls)
- [ ] Feedback channels established (issues template, discussions, form)
- [ ] Triage cadence and SLAs defined (e.g., weekly summaries)

## Release Management

- [ ] Changelog updated (docs/RELEASE_NOTES.md)
- [ ] Version bump strategy agreed (SemVer)
- [ ] Tagging and packaging path verified (source distribution)

## Beta Release Gates

- [ ] All above [DONE]; coverage >=95%, zero warnings/skips, soak pass
- [ ] Manual validation: LLM context injection (sandbox/working_nca_client.py)
- [ ] Tag release: v1.0-beta (after CI/CD gates line 209)
- [ ] Green CI across supported Python versions
- [ ] Security scan: no critical/high issues introduced since last pass
- [ ] Docs reflect the exact setup that CI uses
- [ ] Reproducible quickstart from a fresh clone succeeds in <15 minutes
- [ ] Baseline performance numbers documented with acceptance thresholds
- [ ] Support/onboarding ready; issues routed and tracked