-- Update CLI Entry Points Investigation Results
-- Based on comprehensive investigation completed 2025-06-07

-- First, update the main component record with revised effort estimate and investigation notes
UPDATE components 
SET 
    effort_hours = 6,  -- Increased from 4 to 6 based on deeper investigation
    notes = 'INVESTIGATED 2025-06-07: Root cause identified - missing optional dependencies (asyncpg, aioredis) causing cascade import failures. Core CLI deps (typer, rich, alembic) available in Poetry env. Issue is optional dependency graceful degradation, not basic CLI framework. Fix in progress: Phase 1 complete (core deps), Phase 2 discovered deeper import chain issues.',
    file_path = 'src/neuroca/cli/main.py'  -- Corrected path based on investigation
WHERE component_name = 'CLI Entry Points';

-- Insert or update detailed usage analysis based on investigation
INSERT OR REPLACE INTO component_usage_analysis (
    component_id,
    expected_usage,
    actual_integration_status,
    missing_dependencies,
    integration_issues,
    usage_method,
    working_status,
    priority_to_fix,
    complexity_to_fix,
    current_file_paths,
    entry_points,
    dependencies_on,
    dependencies_from,
    performance_impact,
    documentation_status,
    testing_status,
    production_ready
) VALUES (
    34,  -- CLI Entry Points component_id
    'Command-line interface for NCA operations: neuroca --help, neuroca health, neuroca memory, neuroca llm, etc.',
    'Core CLI framework (typer, rich, alembic) installed in Poetry environment. Main CLI module loads but cascade import failures from optional dependencies prevent full functionality.',
    'asyncpg (PostgreSQL connections), aioredis (Redis backend), tabulate (table formatting). Optional deps treated as required causing hard failures.',
    'Import chain cascade failure: neuroca.cli.main -> neuroca.cli.commands.llm -> neuroca.integration.manager -> neuroca.memory.manager -> neuroca.memory.backends.sql_backend -> neuroca.db.connections.postgres -> asyncpg (UNDEFINED). CLI environment config issues: missing CLIError class, incorrect log paths.',
    'Poetry environment: poetry run neuroca --help (partially works with warnings)',
    'Broken',
    'CRITICAL',
    'MEDIUM',  -- Infrastructure is sound, issue is dependency management
    'src/neuroca/cli/main.py, src/neuroca/cli/commands/, pyproject.toml entry points configured',
    'Configured in pyproject.toml: neuroca = "neuroca.cli.main:app", neuroca-api = "neuroca.api.main:start", neuroca-worker = "neuroca.infrastructure.worker:start"',
    'typer>=0.9.0, rich>=13.4.0, alembic>=1.11.0, asyncpg (optional), aioredis (optional), tabulate',
    'LLM Integration Manager, Memory Manager, Database Connections, Health System',
    'None identified during investigation',
    'Well-documented CLI structure and commands in codebase',
    'Needs CLI integration tests to prevent regression',
    'No - blocked by optional dependency cascade failures'
);

-- Add specific issues found during investigation
INSERT OR REPLACE INTO component_issues (component_id, issue_description, severity) 
VALUES 
    (34, 'Missing asyncpg dependency causing NameError in neuroca.db.connections.postgres line 578', 'High'),
    (34, 'Missing aioredis dependency preventing Redis backend functionality', 'Medium'),
    (34, 'CLIError class undefined causing CLI environment setup failure', 'Medium'),
    (34, 'CLI log path hardcoded to user home instead of project structure', 'Low'),
    (34, 'Missing neuroca.db.connection module preventing db command functionality', 'Medium');

-- Verify the updates
SELECT 'Updated Component Record:' as info;
SELECT component_name, category_name, status_name, effort_hours, notes 
FROM component_overview 
WHERE component_name = 'CLI Entry Points';

SELECT 'Usage Analysis Record:' as info;
SELECT working_status, priority_to_fix, complexity_to_fix, missing_dependencies, integration_issues
FROM component_usage_analysis 
WHERE component_id = 34;

SELECT 'Identified Issues:' as info;
SELECT issue_description, severity 
FROM component_issues 
WHERE component_id = 34;
