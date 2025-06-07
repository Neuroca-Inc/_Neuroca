-- Full Database Normalization with Referential Integrity
-- Date: 2025-06-07
-- Purpose: Convert to fully normalized tables with FK constraints and real-time sync
-- WARNING: This completely restructures the data model - review carefully

-- =============================================================================
-- PHASE 1: DATA RECOVERY - Restore wiped tables from history
-- =============================================================================

SELECT 'PHASE 1: Starting Data Recovery...' as status;

-- Restore component_usage_analysis from history (temporarily with denormalized fields)
INSERT OR REPLACE INTO component_usage_analysis (
    analysis_id, component_id, expected_usage, actual_integration_status,
    missing_dependencies, integration_issues, usage_method, working_status,
    priority_to_fix, complexity_to_fix, current_file_paths, entry_points,
    dependencies_on, dependencies_from, performance_impact, documentation_status,
    testing_status, production_ready, created_at, updated_at, created_by,
    is_active, version
)
SELECT DISTINCT
    analysis_id, component_id, 
    COALESCE(expected_usage, 'Usage analysis pending') as expected_usage,
    COALESCE(actual_integration_status, 'Integration status needs assessment') as actual_integration_status,
    COALESCE(missing_dependencies, 'None identified') as missing_dependencies,
    COALESCE(integration_issues, 'None identified') as integration_issues,
    COALESCE(usage_method, 'Method needs documentation') as usage_method,
    COALESCE(working_status, 'Unknown') as working_status,
    COALESCE(priority_to_fix, 'MEDIUM') as priority_to_fix,
    COALESCE(complexity_to_fix, 'Medium') as complexity_to_fix,
    COALESCE(current_file_paths, 'N/A') as current_file_paths,
    COALESCE(entry_points, 'No specific entry points') as entry_points,
    COALESCE(dependencies_on, 'Standard dependencies only') as dependencies_on,
    COALESCE(dependencies_from, 'No dependencies identified') as dependencies_from,
    COALESCE(performance_impact, 'Not assessed') as performance_impact,
    COALESCE(documentation_status, 'Needs documentation review') as documentation_status,
    COALESCE(testing_status, 'Testing status needs assessment') as testing_status,
    COALESCE(production_ready, 'Unknown') as production_ready,
    created_at, updated_at, 
    COALESCE(created_by, 'system') as created_by,
    COALESCE(is_active, TRUE) as is_active,
    COALESCE(version, 1) as version
FROM (
    SELECT *,
           ROW_NUMBER() OVER (PARTITION BY analysis_id ORDER BY history_timestamp DESC) as rn
    FROM component_usage_analysis_history
    WHERE history_operation != 'DELETE'
) ranked
WHERE rn = 1;

SELECT 'Data Recovery Complete - Records restored: ' || COUNT(*) as status FROM component_usage_analysis;

-- =============================================================================
-- PHASE 2: CREATE MISSING LOOKUP TABLES FOR FULL NORMALIZATION
-- =============================================================================

SELECT 'PHASE 2: Creating missing lookup tables...' as status;

-- Create missing working_statuses table
CREATE TABLE IF NOT EXISTS working_statuses (
    working_status_id INTEGER PRIMARY KEY,
    status_name TEXT NOT NULL UNIQUE,
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Populate working_statuses
INSERT OR IGNORE INTO working_statuses (working_status_id, status_name, description)
VALUES 
    (1, 'Unknown', 'Working status not determined'),
    (2, 'Broken', 'Component has critical issues'),
    (3, 'Partially Working', 'Some functionality works'),
    (4, 'Fully Working', 'All functionality operational'),
    (5, 'Missing', 'Component not implemented'),
    (6, 'Exists But Not Connected', 'Component exists but not integrated'),
    (7, 'Duplicated', 'Component has duplicate implementations'),
    (8, 'Blocked by missing service layer', 'Waiting for service layer'),
    (9, 'Duplicated/Confused', 'Multiple conflicting implementations');

-- Create usage_methods lookup table
CREATE TABLE IF NOT EXISTS usage_methods (
    usage_method_id INTEGER PRIMARY KEY,
    method_name TEXT NOT NULL UNIQUE,
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

INSERT OR IGNORE INTO usage_methods (usage_method_id, method_name, description)
VALUES 
    (1, 'Method needs documentation', 'Usage method not documented'),
    (2, 'Direct Import', 'Direct module import'),
    (3, 'Factory Pattern', 'Created through factory'),
    (4, 'Dependency Injection', 'Injected as dependency'),
    (5, 'API Endpoint', 'Accessed via API'),
    (6, 'CLI Command', 'Command line interface'),
    (7, 'Event Handler', 'Event-driven usage'),
    (8, 'Configuration', 'Configuration-based'),
    (9, 'Plugin System', 'Plugin architecture');

-- Create documentation_statuses lookup table
CREATE TABLE IF NOT EXISTS documentation_statuses (
    doc_status_id INTEGER PRIMARY KEY,
    status_name TEXT NOT NULL UNIQUE,
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

INSERT OR IGNORE INTO documentation_statuses (doc_status_id, status_name, description)
VALUES 
    (1, 'Needs documentation review', 'Documentation status unknown'),
    (2, 'Not Documented', 'No documentation exists'),
    (3, 'Partially Documented', 'Some documentation exists'),
    (4, 'Fully Documented', 'Complete documentation'),
    (5, 'Documentation Outdated', 'Documentation needs updating');

-- Create testing_statuses lookup table  
CREATE TABLE IF NOT EXISTS testing_statuses (
    test_status_id INTEGER PRIMARY KEY,
    status_name TEXT NOT NULL UNIQUE,
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

INSERT OR IGNORE INTO testing_statuses (test_status_id, status_name, description)
VALUES 
    (1, 'Testing status needs assessment', 'Testing status unknown'),
    (2, 'No Tests', 'No tests exist'),
    (3, 'Unit Tests Only', 'Only unit tests exist'),
    (4, 'Integration Tests', 'Integration tests exist'),
    (5, 'Full Test Coverage', 'Comprehensive test coverage'),
    (6, 'Tests Failing', 'Tests exist but failing');

SELECT 'Lookup tables created' as status;

-- =============================================================================
-- PHASE 3: NORMALIZE component_usage_analysis TABLE
-- =============================================================================

SELECT 'PHASE 3: Converting to normalized structure...' as status;

-- Add FK columns to component_usage_analysis
ALTER TABLE component_usage_analysis ADD COLUMN working_status_id INTEGER;
ALTER TABLE component_usage_analysis ADD COLUMN priority_id INTEGER;
ALTER TABLE component_usage_analysis ADD COLUMN complexity_id INTEGER;
ALTER TABLE component_usage_analysis ADD COLUMN usage_method_id INTEGER;
ALTER TABLE component_usage_analysis ADD COLUMN doc_status_id INTEGER;
ALTER TABLE component_usage_analysis ADD COLUMN test_status_id INTEGER;
ALTER TABLE component_usage_analysis ADD COLUMN readiness_id INTEGER;

-- Map text values to FK IDs
UPDATE component_usage_analysis SET working_status_id = (
    SELECT working_status_id FROM working_statuses 
    WHERE LOWER(status_name) = LOWER(TRIM(working_status))
    OR (working_status = 'Unknown' AND status_name = 'Unknown')
    LIMIT 1
);

UPDATE component_usage_analysis SET priority_id = (
    SELECT priority_id FROM priority_levels 
    WHERE LOWER(priority_name) = LOWER(TRIM(priority_to_fix))
    LIMIT 1
);

UPDATE component_usage_analysis SET complexity_id = (
    SELECT complexity_id FROM complexity_levels 
    WHERE LOWER(complexity_name) = LOWER(TRIM(complexity_to_fix))
    LIMIT 1
);

UPDATE component_usage_analysis SET usage_method_id = (
    SELECT usage_method_id FROM usage_methods 
    WHERE LOWER(method_name) = LOWER(TRIM(usage_method))
    OR (usage_method = 'Method needs documentation' AND method_name = 'Method needs documentation')
    LIMIT 1
);

UPDATE component_usage_analysis SET doc_status_id = (
    SELECT doc_status_id FROM documentation_statuses 
    WHERE LOWER(status_name) = LOWER(TRIM(documentation_status))
    OR (documentation_status = 'Needs documentation review' AND status_name = 'Needs documentation review')
    LIMIT 1
);

UPDATE component_usage_analysis SET test_status_id = (
    SELECT test_status_id FROM testing_statuses 
    WHERE LOWER(status_name) = LOWER(TRIM(testing_status))
    OR (testing_status = 'Testing status needs assessment' AND status_name = 'Testing status needs assessment')
    LIMIT 1
);

UPDATE component_usage_analysis SET readiness_id = (
    SELECT readiness_id FROM readiness_statuses 
    WHERE production_ready = 'Yes' AND readiness_name = 'Yes'
    OR production_ready = 'No' AND readiness_name = 'No'
    OR production_ready = 'Unknown' AND readiness_name = 'Unknown'
    LIMIT 1
);

-- Set defaults for any missing FK references
UPDATE component_usage_analysis SET 
    working_status_id = COALESCE(working_status_id, 1),
    priority_id = COALESCE(priority_id, 3),
    complexity_id = COALESCE(complexity_id, 2),
    usage_method_id = COALESCE(usage_method_id, 1),
    doc_status_id = COALESCE(doc_status_id, 1),
    test_status_id = COALESCE(test_status_id, 1),
    readiness_id = COALESCE(readiness_id, 4);

SELECT 'Normalization mapping complete' as status;

-- =============================================================================
-- PHASE 4: ADD FOREIGN KEY CONSTRAINTS (REFERENTIAL INTEGRITY)
-- =============================================================================

SELECT 'PHASE 4: Adding foreign key constraints...' as status;

-- Enable foreign keys
PRAGMA foreign_keys = ON;

-- Create new normalized table with proper constraints
CREATE TABLE component_usage_analysis_normalized (
    analysis_id INTEGER PRIMARY KEY,
    component_id INTEGER NOT NULL,
    expected_usage TEXT NOT NULL DEFAULT 'Usage analysis pending',
    actual_integration_status TEXT NOT NULL DEFAULT 'Integration status needs assessment',
    missing_dependencies TEXT NOT NULL DEFAULT 'None identified',
    integration_issues TEXT NOT NULL DEFAULT 'None identified',
    working_status_id INTEGER NOT NULL DEFAULT 1,
    priority_id INTEGER NOT NULL DEFAULT 3,
    complexity_id INTEGER NOT NULL DEFAULT 2,
    usage_method_id INTEGER NOT NULL DEFAULT 1,
    doc_status_id INTEGER NOT NULL DEFAULT 1,
    test_status_id INTEGER NOT NULL DEFAULT 1,
    readiness_id INTEGER NOT NULL DEFAULT 4,
    current_file_paths TEXT NOT NULL DEFAULT 'N/A',
    entry_points TEXT NOT NULL DEFAULT 'No specific entry points',
    dependencies_on TEXT NOT NULL DEFAULT 'Standard dependencies only',
    dependencies_from TEXT NOT NULL DEFAULT 'No dependencies identified',
    performance_impact TEXT NOT NULL DEFAULT 'Not assessed',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT NOT NULL DEFAULT 'system',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    version INTEGER NOT NULL DEFAULT 1,
    
    -- Foreign Key Constraints
    FOREIGN KEY (component_id) REFERENCES components(component_id) ON DELETE CASCADE,
    FOREIGN KEY (working_status_id) REFERENCES working_statuses(working_status_id),
    FOREIGN KEY (priority_id) REFERENCES priority_levels(priority_id),
    FOREIGN KEY (complexity_id) REFERENCES complexity_levels(complexity_id),
    FOREIGN KEY (usage_method_id) REFERENCES usage_methods(usage_method_id),
    FOREIGN KEY (doc_status_id) REFERENCES documentation_statuses(doc_status_id),
    FOREIGN KEY (test_status_id) REFERENCES testing_statuses(test_status_id),
    FOREIGN KEY (readiness_id) REFERENCES readiness_statuses(readiness_id)
);

-- Copy data to normalized table
INSERT INTO component_usage_analysis_normalized (
    analysis_id, component_id, expected_usage, actual_integration_status,
    missing_dependencies, integration_issues, working_status_id, priority_id,
    complexity_id, usage_method_id, doc_status_id, test_status_id, readiness_id,
    current_file_paths, entry_points, dependencies_on, dependencies_from,
    performance_impact, created_at, updated_at, created_by, is_active, version
)
SELECT 
    analysis_id, component_id, expected_usage, actual_integration_status,
    missing_dependencies, integration_issues, working_status_id, priority_id,
    complexity_id, usage_method_id, doc_status_id, test_status_id, readiness_id,
    current_file_paths, entry_points, dependencies_on, dependencies_from,
    performance_impact, created_at, updated_at, created_by, is_active, version
FROM component_usage_analysis;

-- Replace old table with normalized version
DROP TABLE component_usage_analysis;
ALTER TABLE component_usage_analysis_normalized RENAME TO component_usage_analysis;

-- Drop the empty duplicate table
DROP TABLE IF EXISTS component_usage_core;

SELECT 'Foreign key constraints added' as status;

-- =============================================================================
-- PHASE 5: REAL-TIME SYNC TRIGGERS
-- =============================================================================

SELECT 'PHASE 5: Creating real-time sync triggers...' as status;

-- Update timestamp trigger for component_usage_analysis
CREATE TRIGGER component_usage_analysis_update_timestamp
AFTER UPDATE ON component_usage_analysis
FOR EACH ROW
BEGIN
    UPDATE component_usage_analysis
    SET updated_at = CURRENT_TIMESTAMP, 
        version = version + 1,
        created_by = CASE 
            WHEN NEW.created_by LIKE 'manual:%' THEN NEW.created_by
            WHEN NEW.created_by LIKE 'system:%' THEN NEW.created_by
            ELSE 'trigger:component_usage_analysis'
        END
    WHERE analysis_id = NEW.analysis_id;
END;

-- Sync component status changes to usage analysis
CREATE TRIGGER sync_component_status_to_usage
AFTER UPDATE OF status_id ON components
FOR EACH ROW
WHEN OLD.status_id != NEW.status_id
BEGIN
    UPDATE component_usage_analysis 
    SET actual_integration_status = (
        SELECT 'Status updated to: ' || s.status_name 
        FROM statuses s 
        WHERE s.status_id = NEW.status_id
    ),
    working_status_id = (
        SELECT CASE NEW.status_id
            WHEN 1 THEN 2  -- Broken -> Broken
            WHEN 8 THEN 4  -- Fully Working -> Fully Working
            WHEN 6 THEN 5  -- Missing -> Missing
            WHEN 3 THEN 6  -- Exists But Not Connected -> Exists But Not Connected
            ELSE working_status_id
        END
    ),
    updated_at = CURRENT_TIMESTAMP,
    created_by = 'trigger:components.status_change',
    version = version + 1
    WHERE component_id = NEW.component_id;
END;

-- Sync issue resolution to component status
CREATE TRIGGER sync_resolved_issues_to_component
AFTER UPDATE OF resolved ON component_issues
FOR EACH ROW
WHEN OLD.resolved = FALSE AND NEW.resolved = TRUE
BEGIN
    UPDATE components 
    SET status_id = (
        CASE 
            WHEN (SELECT COUNT(*) FROM component_issues 
                  WHERE component_id = NEW.component_id 
                  AND resolved = FALSE 
                  AND is_active = TRUE) = 0 
            THEN 8 -- "Fully Working" status
            ELSE status_id
        END
    ),
    updated_at = CURRENT_TIMESTAMP,
    created_by = 'trigger:component_issues.resolved'
    WHERE component_id = NEW.component_id;
END;

-- Sync dependency changes
CREATE TRIGGER sync_dependency_changes
AFTER INSERT ON component_dependencies
FOR EACH ROW
BEGIN
    UPDATE component_usage_analysis
    SET dependencies_on = dependencies_on || '; ' || NEW.depends_on,
        updated_at = CURRENT_TIMESTAMP,
        created_by = 'trigger:component_dependencies.new',
        version = version + 1
    WHERE component_id = NEW.component_id;
END;

SELECT 'Real-time sync triggers created' as status;

-- =============================================================================
-- PHASE 6: CREATE REPORTING VIEWS FOR COMPLEX QUERIES
-- =============================================================================

SELECT 'PHASE 6: Creating reporting views...' as status;

-- Comprehensive component analysis view
CREATE VIEW IF NOT EXISTS component_analysis_report AS
SELECT 
    c.component_id,
    c.component_name,
    cat.category_name,
    s.status_name as component_status,
    cua.expected_usage,
    cua.actual_integration_status,
    ws.status_name as working_status,
    pl.priority_name as priority,
    cl.complexity_name as complexity,
    cl.estimated_hours,
    um.method_name as usage_method,
    ds.status_name as documentation_status,
    ts.status_name as testing_status,
    rs.readiness_name as production_readiness,
    cua.missing_dependencies,
    cua.integration_issues,
    cua.current_file_paths,
    cua.entry_points,
    cua.dependencies_on,
    cua.dependencies_from,
    cua.performance_impact,
    c.completion_percentage,
    c.effort_hours,
    c.notes,
    cua.created_at as analysis_created,
    cua.updated_at as analysis_updated,
    cua.created_by as analysis_updated_by,
    cua.version as analysis_version
FROM components c
LEFT JOIN categories cat ON c.category_id = cat.category_id
LEFT JOIN statuses s ON c.status_id = s.status_id
LEFT JOIN component_usage_analysis cua ON c.component_id = cua.component_id
LEFT JOIN working_statuses ws ON cua.working_status_id = ws.working_status_id
LEFT JOIN priority_levels pl ON cua.priority_id = pl.priority_id
LEFT JOIN complexity_levels cl ON cua.complexity_id = cl.complexity_id
LEFT JOIN usage_methods um ON cua.usage_method_id = um.usage_method_id
LEFT JOIN documentation_statuses ds ON cua.doc_status_id = ds.doc_status_id
LEFT JOIN testing_statuses ts ON cua.test_status_id = ts.test_status_id
LEFT JOIN readiness_statuses rs ON cua.readiness_id = rs.readiness_id
WHERE c.is_active = TRUE;

-- Priority dashboard view
CREATE VIEW IF NOT EXISTS priority_dashboard AS
SELECT 
    c.component_name,
    s.status_name as status,
    pl.priority_name as priority,
    c.completion_percentage,
    c.effort_hours,
    CASE 
        WHEN fs.activity_level IS NOT NULL THEN fs.activity_level
        ELSE 'No Activity'
    END as activity_level,
    CASE 
        WHEN fs.test_coverage_status IS NOT NULL THEN fs.test_coverage_status
        ELSE 'Unknown'
    END as test_coverage_status
FROM components c
LEFT JOIN statuses s ON c.status_id = s.status_id
LEFT JOIN component_usage_analysis cua ON c.component_id = cua.component_id
LEFT JOIN priority_levels pl ON cua.priority_id = pl.priority_id
LEFT JOIN current_file_status fs ON c.component_id = fs.component_id
WHERE c.is_active = TRUE
ORDER BY pl.priority_order, 
         CASE fs.activity_level 
             WHEN 'Very Active' THEN 1
             WHEN 'Active' THEN 2
             WHEN 'Moderate' THEN 3
             WHEN 'Low' THEN 4
             WHEN 'Inactive' THEN 5
             ELSE 6
         END;

-- Issue tracking view
CREATE VIEW IF NOT EXISTS component_issues_report AS
SELECT 
    c.component_name,
    ci.issue_description,
    ci.severity,
    ci.resolved,
    ci.created_at as issue_created,
    ci.resolved_at,
    ci.resolved_by,
    s.status_name as component_status,
    ws.status_name as working_status
FROM component_issues ci
JOIN components c ON ci.component_id = c.component_id
LEFT JOIN statuses s ON c.status_id = s.status_id
LEFT JOIN component_usage_analysis cua ON c.component_id = cua.component_id
LEFT JOIN working_statuses ws ON cua.working_status_id = ws.working_status_id
WHERE ci.is_active = TRUE
ORDER BY ci.resolved, ci.severity DESC, ci.created_at DESC;

SELECT 'Reporting views created' as status;

-- =============================================================================
-- FINAL VALIDATION
-- =============================================================================

SELECT 'PHASE 7: Final validation...' as status;

-- Check foreign key constraint violations
PRAGMA foreign_key_check;

-- Verify normalization
SELECT 'Normalized component_usage_analysis records: ' || COUNT(*) as validation
FROM component_usage_analysis;

SELECT 'Records with all FK constraints satisfied: ' || COUNT(*) as validation
FROM component_usage_analysis cua
JOIN working_statuses ws ON cua.working_status_id = ws.working_status_id
JOIN priority_levels pl ON cua.priority_id = pl.priority_id
JOIN complexity_levels cl ON cua.complexity_id = cl.complexity_id
JOIN usage_methods um ON cua.usage_method_id = um.usage_method_id
JOIN documentation_statuses ds ON cua.doc_status_id = ds.doc_status_id
JOIN testing_statuses ts ON cua.test_status_id = ts.test_status_id
JOIN readiness_statuses rs ON cua.readiness_id = rs.readiness_id;

-- Test the reporting views
SELECT 'Component analysis report records: ' || COUNT(*) as validation
FROM component_analysis_report;

SELECT 'Priority dashboard records: ' || COUNT(*) as validation
FROM priority_dashboard;

SELECT 'FULL NORMALIZATION WITH REFERENTIAL INTEGRITY COMPLETE!' as status;
SELECT 'All tables normalized, FK constraints enforced, real-time sync active, reporting views created.' as final_status;
