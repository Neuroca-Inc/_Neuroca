# Critical Security Fix Checklist

This document tracks the remediation status of the critical security issues identified for the Neuroca project. Items are ordered from highest to lowest priority based on potential exploitability and breadth of impact.

## Command Execution Vulnerabilities
- [x] Refactor `subprocess.Popen` usage in `src/neuroca/cli/commands/system.py` to eliminate the possibility of command injection when reading logs.
- [x] Refactor `os.system` call in `src/neuroca/cli/commands/llm.py` to ensure user data cannot influence shell evaluation.
- [x] Refactor `subprocess.run` call in `src/neuroca/monitoring/health/probes.py` to avoid command injection vectors.
- [x] Refactor `subprocess.run` call in `src/neuroca/cli/commands/system.py` to prevent injection through dynamically constructed commands.
- [x] Refactor `subprocess.run` call in `tests/scripts/check_coverage.py` to guard against command injection.

## SQL Injection Vulnerabilities
- [x] Replace dynamic `search_path` assignment with parameterized query in `src/neuroca/db/connections/postgres.py`.
- [x] Replace dynamic `statement_timeout` assignment with parameterized query in `src/neuroca/db/connections/postgres.py`.
- [x] Parameterize competitor query at line 213 in `benchmarks/memory_systems_comparison/competitors/sqlite_memory.py`.
- [x] Parameterize competitor query at line 217 in `benchmarks/memory_systems_comparison/competitors/sqlite_memory.py`.

## Secrets Management
- [x] Remove hardcoded `SECRET_KEY` from `src/neuroca/config/default.py`.
- [x] Remove hardcoded `DEFAULT_PASSWORD` from `tests/factories/users.py`.

## Serialization Risks
- [ ] Replace insecure `pickle.load` usage in `src/neuroca/tools/caching.py`.
- [ ] Replace insecure `pickle.loads` usage in `src/neuroca/tools/caching.py`.

## Cross-Site Scripting (XSS)
- [ ] Sanitize user-controlled input before it is embedded into HTML in `src/neuroca/api/middleware/logging.py`.

## Dependency Vulnerabilities
- [ ] Update `langchain` to at least `0.0.325` (covers CVE-2023-39631, CVE-2023-36281, and CVE-2023-39659).
- [ ] Update `transformers` to at least `4.36.0`.
- [ ] Update `torch` to at least `2.6.0`.

## Runtime Safety Checks
- [ ] Ensure callable validation for `original_store` at `tests/unit/memory/manager/test_transactional_consolidation.py`.
- [ ] Ensure callable validation for `handler` at `src/neuroca/memory/manager/memory_manager.py`.
- [ ] Ensure callable validation for `counter` at `src/neuroca/memory/manager/memory_manager.py`.
- [ ] Ensure callable validation for `getter` at `src/neuroca/core/cognitive_control/decision_maker.py`.

## Prompt Validation Issues
- [ ] Correct duplicate `min_length` arguments across `src/neuroca/integration/prompts/*` files.

## Constructor Argument Issues
- [ ] Provide `backend_type` to `StorageStats` constructors.
- [ ] Add missing `user_id` argument in `src/neuroca/api/routes/memory_v1.py`.

## Notes
- Focus remediation work from top to bottom, ensuring the highest-risk vulnerabilities are addressed first.
- Document each fix with tests or validation steps demonstrating the mitigation.
- Update this checklist as issues are resolved.
