# Code Map — Key Modules & Responsibilities

**Project:** Neuroca  
**Generated:** 2025-11-06  
**Commit:** 563c5ce81e92499cf83c4f674f6dc1ebf86a4906  

---

## Overview

- **Total Modules:** 385
- **Total LOC:** 101,580
- **Top-Level Packages:** 14

## Statistics by Package

| Package | Modules | Total LOC | Avg LOC/Module |
|---------|---------|-----------|----------------|
| __init__ | 1 | 6 | 6 |
| analysis | 4 | 2,814 | 704 |
| api | 31 | 9,760 | 315 |
| cli | 12 | 4,767 | 397 |
| config | 6 | 2,277 | 380 |
| core | 47 | 13,374 | 285 |
| db | 18 | 7,260 | 403 |
| infrastructure | 6 | 12 | 2 |
| integration | 24 | 9,129 | 380 |
| memory | 208 | 35,990 | 173 |
| monitoring | 14 | 8,414 | 601 |
| scripts | 1 | 353 | 353 |
| tools | 10 | 7,146 | 715 |
| utils | 3 | 276 | 92 |

---

## Detailed Module Map


### API Package


#### `routes.metrics`
- **Path:** `src/neuroca/api/routes/metrics.py`
- **LOC:** 600
- **Classes:** 3, **Functions:** 1
- **Responsibility:** API endpoint handlers

#### `routes.system`
- **Path:** `src/neuroca/api/routes/system.py`
- **LOC:** 548
- **Classes:** 6, **Functions:** 0
- **Responsibility:** API endpoint handlers

#### `schemas.requests`
- **Path:** `src/neuroca/api/schemas/requests.py`
- **LOC:** 507
- **Classes:** 10, **Functions:** 0
- **Responsibility:** Data models and schemas

#### `routes.health`
- **Path:** `src/neuroca/api/routes/health.py`
- **LOC:** 471
- **Classes:** 5, **Functions:** 0
- **Responsibility:** API endpoint handlers

#### `routes.integration`
- **Path:** `src/neuroca/api/routes/integration.py`
- **LOC:** 463
- **Classes:** 6, **Functions:** 0
- **Responsibility:** API endpoint handlers

#### `routes.monitoring`
- **Path:** `src/neuroca/api/routes/monitoring.py`
- **LOC:** 459
- **Classes:** 6, **Functions:** 0
- **Responsibility:** API endpoint handlers

#### `websockets.__init__`
- **Path:** `src/neuroca/api/websockets/__init__.py`
- **LOC:** 450
- **Classes:** 3, **Functions:** 1

#### `routes.llm`
- **Path:** `src/neuroca/api/routes/llm.py`
- **LOC:** 442
- **Classes:** 3, **Functions:** 2
- **Responsibility:** API endpoint handlers

#### `middleware.authentication`
- **Path:** `src/neuroca/api/middleware/authentication.py`
- **LOC:** 437
- **Classes:** 5, **Functions:** 12

#### `schemas.memory`
- **Path:** `src/neuroca/api/schemas/memory.py`
- **LOC:** 433
- **Classes:** 13, **Functions:** 0
- **Responsibility:** Data models and schemas

#### `websockets.handlers`
- **Path:** `src/neuroca/api/websockets/handlers.py`
- **LOC:** 432
- **Classes:** 4, **Functions:** 0

#### `routes.auth`
- **Path:** `src/neuroca/api/routes/auth.py`
- **LOC:** 407
- **Classes:** 7, **Functions:** 4
- **Responsibility:** API endpoint handlers

#### `routes.memory_v1`
- **Path:** `src/neuroca/api/routes/memory_v1.py`
- **LOC:** 404
- **Classes:** 0, **Functions:** 6
- **Responsibility:** API endpoint handlers

#### `dependencies`
- **Path:** `src/neuroca/api/dependencies.py`
- **LOC:** 385
- **Classes:** 0, **Functions:** 7

#### `schemas.common`
- **Path:** `src/neuroca/api/schemas/common.py`
- **LOC:** 383
- **Classes:** 16, **Functions:** 1
- **Responsibility:** Data models and schemas

### MEMORY Package


#### `manager.memory_manager`
- **Path:** `src/neuroca/memory/manager/memory_manager.py`
- **LOC:** 2004
- **Classes:** 1, **Functions:** 0
- **Responsibility:** Orchestration and management

#### `tiers.base.core`
- **Path:** `src/neuroca/memory/tiers/base/core.py`
- **LOC:** 792
- **Classes:** 1, **Functions:** 0

#### `lymphatic.abstractor`
- **Path:** `src/neuroca/memory/lymphatic/abstractor.py`
- **LOC:** 747
- **Classes:** 2, **Functions:** 0

#### `tubules.weights`
- **Path:** `src/neuroca/memory/tubules/weights.py`
- **LOC:** 623
- **Classes:** 5, **Functions:** 3

#### `tubules.pathways`
- **Path:** `src/neuroca/memory/tubules/pathways.py`
- **LOC:** 600
- **Classes:** 4, **Functions:** 0

#### `service`
- **Path:** `src/neuroca/memory/service.py`
- **LOC:** 593
- **Classes:** 5, **Functions:** 0
- **Responsibility:** Business logic service

#### `adapters.storage_adapters`
- **Path:** `src/neuroca/memory/adapters/storage_adapters.py`
- **LOC:** 552
- **Classes:** 3, **Functions:** 0
- **Responsibility:** Data persistence adapter

#### `tubules.connections`
- **Path:** `src/neuroca/memory/tubules/connections.py`
- **LOC:** 513
- **Classes:** 4, **Functions:** 0

#### `annealing.__init__`
- **Path:** `src/neuroca/memory/annealing/__init__.py`
- **LOC:** 494
- **Classes:** 14, **Functions:** 1

#### `lymphatic.scheduler`
- **Path:** `src/neuroca/memory/lymphatic/scheduler.py`
- **LOC:** 483
- **Classes:** 4, **Functions:** 0

#### `tiers.ltm.core`
- **Path:** `src/neuroca/memory/tiers/ltm/core.py`
- **LOC:** 457
- **Classes:** 1, **Functions:** 0

#### `manager.maintenance`
- **Path:** `src/neuroca/memory/manager/maintenance.py`
- **LOC:** 452
- **Classes:** 2, **Functions:** 0
- **Responsibility:** Orchestration and management

#### `backends.sqlite.core`
- **Path:** `src/neuroca/memory/backends/sqlite/core.py`
- **LOC:** 447
- **Classes:** 1, **Functions:** 0
- **Responsibility:** Data persistence adapter

#### `tubules.__init__`
- **Path:** `src/neuroca/memory/tubules/__init__.py`
- **LOC:** 442
- **Classes:** 9, **Functions:** 0

#### `memory_decay`
- **Path:** `src/neuroca/memory/memory_decay.py`
- **LOC:** 431
- **Classes:** 2, **Functions:** 0

### CORE Package


#### `health.thresholds`
- **Path:** `src/neuroca/core/health/thresholds.py`
- **LOC:** 863
- **Classes:** 7, **Functions:** 4

#### `cognitive_control.goal_manager`
- **Path:** `src/neuroca/core/cognitive_control/goal_manager.py`
- **LOC:** 706
- **Classes:** 3, **Functions:** 0
- **Responsibility:** Orchestration and management

#### `utils.validation`
- **Path:** `src/neuroca/core/utils/validation.py`
- **LOC:** 695
- **Classes:** 1, **Functions:** 16
- **Responsibility:** Utility functions

#### `health.calculator`
- **Path:** `src/neuroca/core/health/calculator.py`
- **LOC:** 615
- **Classes:** 2, **Functions:** 4

#### `health.dynamics`
- **Path:** `src/neuroca/core/health/dynamics.py`
- **LOC:** 561
- **Classes:** 7, **Functions:** 3

#### `models.base`
- **Path:** `src/neuroca/core/models/base.py`
- **LOC:** 555
- **Classes:** 14, **Functions:** 0
- **Responsibility:** Data models and schemas

#### `utils.serialization`
- **Path:** `src/neuroca/core/utils/serialization.py`
- **LOC:** 536
- **Classes:** 8, **Functions:** 17
- **Responsibility:** Utility functions

#### `health.metadata`
- **Path:** `src/neuroca/core/health/metadata.py`
- **LOC:** 534
- **Classes:** 7, **Functions:** 1

#### `events.system`
- **Path:** `src/neuroca/core/events/system.py`
- **LOC:** 500
- **Classes:** 12, **Functions:** 4

#### `cognitive_control.inhibitor`
- **Path:** `src/neuroca/core/cognitive_control/inhibitor.py`
- **LOC:** 493
- **Classes:** 3, **Functions:** 0

#### `exceptions`
- **Path:** `src/neuroca/core/exceptions.py`
- **LOC:** 489
- **Classes:** 34, **Functions:** 2
- **Responsibility:** Error handling and exceptions

#### `utils.__init__`
- **Path:** `src/neuroca/core/utils/__init__.py`
- **LOC:** 438
- **Classes:** 4, **Functions:** 12
- **Responsibility:** Utility functions

#### `events.handlers`
- **Path:** `src/neuroca/core/events/handlers.py`
- **LOC:** 432
- **Classes:** 13, **Functions:** 2

#### `utils.security`
- **Path:** `src/neuroca/core/utils/security.py`
- **LOC:** 406
- **Classes:** 6, **Functions:** 13
- **Responsibility:** Utility functions

#### `enums`
- **Path:** `src/neuroca/core/enums.py`
- **LOC:** 402
- **Classes:** 8, **Functions:** 1

### INTEGRATION Package


#### `prompts.memory`
- **Path:** `src/neuroca/integration/prompts/memory.py`
- **LOC:** 652
- **Classes:** 0, **Functions:** 7

#### `langchain.memory`
- **Path:** `src/neuroca/integration/langchain/memory.py`
- **LOC:** 598
- **Classes:** 5, **Functions:** 0

#### `context.injection`
- **Path:** `src/neuroca/integration/context/injection.py`
- **LOC:** 584
- **Classes:** 6, **Functions:** 1

#### `adapters.vertexai`
- **Path:** `src/neuroca/integration/adapters/vertexai.py`
- **LOC:** 569
- **Classes:** 2, **Functions:** 0
- **Responsibility:** Data persistence adapter

#### `prompts.reasoning`
- **Path:** `src/neuroca/integration/prompts/reasoning.py`
- **LOC:** 555
- **Classes:** 11, **Functions:** 2

#### `langchain.chains`
- **Path:** `src/neuroca/integration/langchain/chains.py`
- **LOC:** 523
- **Classes:** 5, **Functions:** 2

#### `adapters.openai`
- **Path:** `src/neuroca/integration/adapters/openai.py`
- **LOC:** 467
- **Classes:** 2, **Functions:** 0
- **Responsibility:** Data persistence adapter

#### `context.manager`
- **Path:** `src/neuroca/integration/context/manager.py`
- **LOC:** 458
- **Classes:** 6, **Functions:** 0
- **Responsibility:** Orchestration and management

#### `manager`
- **Path:** `src/neuroca/integration/manager.py`
- **LOC:** 442
- **Classes:** 1, **Functions:** 0
- **Responsibility:** Orchestration and management

#### `langchain.tools`
- **Path:** `src/neuroca/integration/langchain/tools.py`
- **LOC:** 442
- **Classes:** 7, **Functions:** 4

#### `adapters.anthropic`
- **Path:** `src/neuroca/integration/adapters/anthropic.py`
- **LOC:** 442
- **Classes:** 3, **Functions:** 0
- **Responsibility:** Data persistence adapter

#### `prompts.templates`
- **Path:** `src/neuroca/integration/prompts/templates.py`
- **LOC:** 433
- **Classes:** 7, **Functions:** 0

#### `adapters.base`
- **Path:** `src/neuroca/integration/adapters/base.py`
- **LOC:** 424
- **Classes:** 13, **Functions:** 0
- **Responsibility:** Data persistence adapter

#### `context.__init__`
- **Path:** `src/neuroca/integration/context/__init__.py`
- **LOC:** 399
- **Classes:** 4, **Functions:** 0

#### `adapters.ollama`
- **Path:** `src/neuroca/integration/adapters/ollama.py`
- **LOC:** 396
- **Classes:** 2, **Functions:** 0
- **Responsibility:** Data persistence adapter

### DB Package


#### `connections.postgres`
- **Path:** `src/neuroca/db/connections/postgres.py`
- **LOC:** 743
- **Classes:** 4, **Functions:** 5

#### `connections.__init__`
- **Path:** `src/neuroca/db/connections/__init__.py`
- **LOC:** 677
- **Classes:** 8, **Functions:** 15

#### `connections.redis`
- **Path:** `src/neuroca/db/connections/redis.py`
- **LOC:** 672
- **Classes:** 1, **Functions:** 3

#### `connections.neo4j`
- **Path:** `src/neuroca/db/connections/neo4j.py`
- **LOC:** 615
- **Classes:** 4, **Functions:** 0

#### `repositories.ltm`
- **Path:** `src/neuroca/db/repositories/ltm.py`
- **LOC:** 577
- **Classes:** 1, **Functions:** 0

#### `repositories.mtm`
- **Path:** `src/neuroca/db/repositories/mtm.py`
- **LOC:** 533
- **Classes:** 1, **Functions:** 0

#### `repositories.stm`
- **Path:** `src/neuroca/db/repositories/stm.py`
- **LOC:** 532
- **Classes:** 1, **Functions:** 0

#### `connections.mongo`
- **Path:** `src/neuroca/db/connections/mongo.py`
- **LOC:** 435
- **Classes:** 2, **Functions:** 0

#### `migrations.__init__`
- **Path:** `src/neuroca/db/migrations/__init__.py`
- **LOC:** 378
- **Classes:** 6, **Functions:** 1

#### `schemas.mtm`
- **Path:** `src/neuroca/db/schemas/mtm.py`
- **LOC:** 375
- **Classes:** 4, **Functions:** 2
- **Responsibility:** Data models and schemas

#### `repositories.base`
- **Path:** `src/neuroca/db/repositories/base.py`
- **LOC:** 340
- **Classes:** 5, **Functions:** 0

#### `__init__`
- **Path:** `src/neuroca/db/__init__.py`
- **LOC:** 313
- **Classes:** 5, **Functions:** 9

#### `schemas.ltm`
- **Path:** `src/neuroca/db/schemas/ltm.py`
- **LOC:** 281
- **Classes:** 10, **Functions:** 0
- **Responsibility:** Data models and schemas

#### `schemas.stm`
- **Path:** `src/neuroca/db/schemas/stm.py`
- **LOC:** 244
- **Classes:** 5, **Functions:** 0
- **Responsibility:** Data models and schemas

#### `repositories.__init__`
- **Path:** `src/neuroca/db/repositories/__init__.py`
- **LOC:** 208
- **Classes:** 7, **Functions:** 0

### CLI Package


#### `commands.system`
- **Path:** `src/neuroca/cli/commands/system.py`
- **LOC:** 1143
- **Classes:** 0, **Functions:** 40

#### `utils.formatting`
- **Path:** `src/neuroca/cli/utils/formatting.py`
- **LOC:** 627
- **Classes:** 2, **Functions:** 17
- **Responsibility:** Utility functions

#### `commands.llm`
- **Path:** `src/neuroca/cli/commands/llm.py`
- **LOC:** 580
- **Classes:** 2, **Functions:** 11

#### `commands.memory`
- **Path:** `src/neuroca/cli/commands/memory.py`
- **LOC:** 424
- **Classes:** 0, **Functions:** 10

#### `utils.__init__`
- **Path:** `src/neuroca/cli/utils/__init__.py`
- **LOC:** 415
- **Classes:** 5, **Functions:** 8
- **Responsibility:** Utility functions

#### `utils.validation`
- **Path:** `src/neuroca/cli/utils/validation.py`
- **LOC:** 358
- **Classes:** 1, **Functions:** 16
- **Responsibility:** Utility functions

#### `main`
- **Path:** `src/neuroca/cli/main.py`
- **LOC:** 357
- **Classes:** 2, **Functions:** 5

#### `commands.db`
- **Path:** `src/neuroca/cli/commands/db.py`
- **LOC:** 280
- **Classes:** 0, **Functions:** 12

#### `commands.memory_utils`
- **Path:** `src/neuroca/cli/commands/memory_utils.py`
- **LOC:** 207
- **Classes:** 2, **Functions:** 10
- **Responsibility:** Utility functions

#### `commands.__init__`
- **Path:** `src/neuroca/cli/commands/__init__.py`
- **LOC:** 192
- **Classes:** 0, **Functions:** 7

#### `__init__`
- **Path:** `src/neuroca/cli/__init__.py`
- **LOC:** 140
- **Classes:** 2, **Functions:** 3

#### `commands.health`
- **Path:** `src/neuroca/cli/commands/health.py`
- **LOC:** 44
- **Classes:** 0, **Functions:** 1

### MONITORING Package


#### `metrics.collectors`
- **Path:** `src/neuroca/monitoring/metrics/collectors.py`
- **LOC:** 1531
- **Classes:** 7, **Functions:** 0

#### `health.probes`
- **Path:** `src/neuroca/monitoring/health/probes.py`
- **LOC:** 763
- **Classes:** 8, **Functions:** 1

#### `health.checks`
- **Path:** `src/neuroca/monitoring/health/checks.py`
- **LOC:** 754
- **Classes:** 11, **Functions:** 0

#### `metrics.registry`
- **Path:** `src/neuroca/monitoring/metrics/registry.py`
- **LOC:** 701
- **Classes:** 10, **Functions:** 0

#### `metrics.exporters`
- **Path:** `src/neuroca/monitoring/metrics/exporters.py`
- **LOC:** 678
- **Classes:** 10, **Functions:** 1

#### `logging.formatters`
- **Path:** `src/neuroca/monitoring/logging/formatters.py`
- **LOC:** 533
- **Classes:** 5, **Functions:** 1

#### `logging.__init__`
- **Path:** `src/neuroca/monitoring/logging/__init__.py`
- **LOC:** 518
- **Classes:** 8, **Functions:** 6

#### `tracing.__init__`
- **Path:** `src/neuroca/monitoring/tracing/__init__.py`
- **LOC:** 496
- **Classes:** 2, **Functions:** 8

#### `__init__`
- **Path:** `src/neuroca/monitoring/__init__.py`
- **LOC:** 495
- **Classes:** 3, **Functions:** 5

#### `logging.handlers`
- **Path:** `src/neuroca/monitoring/logging/handlers.py`
- **LOC:** 464
- **Classes:** 6, **Functions:** 0

#### `tracing.middleware`
- **Path:** `src/neuroca/monitoring/tracing/middleware.py`
- **LOC:** 445
- **Classes:** 2, **Functions:** 4

#### `metrics.__init__`
- **Path:** `src/neuroca/monitoring/metrics/__init__.py`
- **LOC:** 402
- **Classes:** 11, **Functions:** 6

#### `health.__init__`
- **Path:** `src/neuroca/monitoring/health/__init__.py`
- **LOC:** 332
- **Classes:** 4, **Functions:** 6

#### `tracing.spans`
- **Path:** `src/neuroca/monitoring/tracing/spans.py`
- **LOC:** 302
- **Classes:** 1, **Functions:** 8

### INFRASTRUCTURE Package


#### `worker`
- **Path:** `src/neuroca/infrastructure/worker.py`
- **LOC:** 7
- **Classes:** 0, **Functions:** 1

#### `__init__`
- **Path:** `src/neuroca/infrastructure/__init__.py`
- **LOC:** 1
- **Classes:** 0, **Functions:** 0

#### `monitoring.__init__`
- **Path:** `src/neuroca/infrastructure/monitoring/__init__.py`
- **LOC:** 1
- **Classes:** 0, **Functions:** 0

#### `docker.__init__`
- **Path:** `src/neuroca/infrastructure/docker/__init__.py`
- **LOC:** 1
- **Classes:** 0, **Functions:** 0

#### `kubernetes.__init__`
- **Path:** `src/neuroca/infrastructure/kubernetes/__init__.py`
- **LOC:** 1
- **Classes:** 0, **Functions:** 0

#### `terraform.__init__`
- **Path:** `src/neuroca/infrastructure/terraform/__init__.py`
- **LOC:** 1
- **Classes:** 0, **Functions:** 0

### UTILS Package


#### `safe_subprocess`
- **Path:** `src/neuroca/utils/safe_subprocess.py`
- **LOC:** 170
- **Classes:** 1, **Functions:** 7

#### `base`
- **Path:** `src/neuroca/utils/base.py`
- **LOC:** 95
- **Classes:** 4, **Functions:** 0

#### `__init__`
- **Path:** `src/neuroca/utils/__init__.py`
- **LOC:** 11
- **Classes:** 0, **Functions:** 0

---

## Hot Spots (Largest Modules)

Modules exceeding 1000 LOC warrant review for potential refactoring.


| Module | LOC | Package |
|--------|-----|---------|
| `memory.manager.memory_manager` | 2004 | memory |
| `monitoring.metrics.collectors` | 1531 | monitoring |
| `analysis.summarization_engine` | 1183 | analysis |
| `cli.commands.system` | 1143 | cli |
| `tools.visualization.memory_visualizer` | 1013 | tools |
| `tools.caching` | 871 | tools |
| `core.health.thresholds` | 863 | core |
| `tools.analysis.memory_analyzer` | 834 | tools |
| `tools.migration.schema_migrator` | 816 | tools |
| `memory.tiers.base.core` | 792 | memory |
| `monitoring.health.probes` | 763 | monitoring |
| `tools.analysis.performance_analyzer` | 759 | tools |
| `monitoring.health.checks` | 754 | monitoring |
| `memory.lymphatic.abstractor` | 747 | memory |
| `db.connections.postgres` | 743 | db |
| `tools.visualization.relationship_visualizer` | 738 | tools |
| `analysis.automation` | 732 | analysis |
| `core.cognitive_control.goal_manager` | 706 | core |
| `monitoring.metrics.registry` | 701 | monitoring |
| `core.utils.validation` | 695 | core |

---

## Entry Points


### API Entry Points

- `api.main` — FastAPI application initialization
- `api.server` — Uvicorn server launcher
- `api.routes.*` — HTTP endpoint handlers

### CLI Entry Points

- `cli.main` — Main CLI application
- `cli.commands.*` — Command implementations

### Worker Entry Points

- `infrastructure.worker` — Background worker launcher
- `memory.manager.consolidation` — Consolidation pipeline
- `memory.manager.decay` — Decay pipeline
