-- Phase 2: Data Migration to Normalized Tables
-- Date: 2025-06-07
-- Purpose: Populate lookup tables and migrate data to normalized structure
-- WARNING: This migrates data but does not delete old tables

-- =============================================================================
-- ENABLE FOREIGN KEY CONSTRAINTS
-- =============================================================================

PRAGMA foreign_keys = ON;

SELECT 'PHASE 2: Starting data migration...' as status;

-- =============================================================================
-- POPULATE LOOKUP TABLES WITH SEED DATA
-- =============================================================================

SELECT 'Populating lookup tables with seed data...' as status;

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

-- Populate usage_methods
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

-- Populate documentation_statuses
INSERT OR IGNORE INTO documentation_statuses (doc_status_id, status_name, description)
VALUES 
    (1, 'Needs documentation review', 'Documentation status unknown'),
    (2, 'Not Documented', 'No documentation exists'),
    (3, 'Partially Documented', 'Some documentation exists'),
    (4, 'Fully Documented', 'Complete documentation'),
    (5, 'Documentation Outdated', 'Documentation needs updating');

-- Populate testing_statuses
INSERT OR IGNORE INTO testing_statuses (test_status_id, status_name, description)
VALUES 
    (1, 'Testing status needs assessment', 'Testing status unknown'),
    (2, 'No Tests', 'No tests exist'),
    (3, 'Unit Tests Only', 'Only unit tests exist'),
    (4, 'Integration Tests', 'Integration tests exist'),
    (5, 'Full Test Coverage', 'Comprehensive test coverage'),
    (6, 'Tests Failing', 'Tests exist but failing');

SELECT 'Lookup tables populated' as status;

-- =============================================================================
-- RESTORE DATA FROM HISTORY TO CURRENT component_usage_analysis TABLE
-- =============================================================================

SELECT 'Restoring data from component_usage_analysis_history...' as status;

-- First, clear any existing data (in case of re-run)
DELETE FROM component_usage_analysis WHERE 1=1;

-- Restore component_usage_analysis from the most recent version in history
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

SELECT 'Data restored - Records: ' || COUNT(*) as status FROM component_usage_analysis;

-- =============================================================================
-- MIGRATE DATA TO NORMALIZED component_usage_analysis_v2 TABLE
-- =============================================================================

SELECT 'Migrating data to normalized component_usage_analysis_v2...' as status;

-- Insert data into normalized table with FK mappings
INSERT INTO component_usage_analysis_v2 (
    analysis_id, component_id, expected_usage, actual_integration_status,
    missing_dependencies, integration_issues, working_status_id, priority_id,
    complexity_id, usage_method_id, doc_status_id, test_status_id, readiness_id,
    current_file_paths, entry_points, dependencies_on, dependencies_from,
    performance_impact, created_at, updated_at, created_by, is_active, version
)
SELECT 
    cua.analysis_id,
    cua.component_id,
    cua.expected_usage,
    cua.actual_integration_status,
    cua.missing_dependencies,
    cua.integration_issues,
    
    -- Map working_status text to working_status_id
    COALESCE((
        SELECT working_status_id FROM working_statuses 
        WHERE LOWER(TRIM(status_name)) = LOWER(TRIM(cua.working_status))
        LIMIT 1
    ), 1) as working_status_id,
    
    -- Map priority_to_fix text to priority_id
    COALESCE((
        SELECT priority_id FROM priority_levels 
        WHERE LOWER(TRIM(priority_name)) = LOWER(TRIM(cua.priority_to_fix))
        LIMIT 1
    ), 3) as priority_id,
    
    -- Map complexity_to_fix text to complexity_id
    COALESCE((
        SELECT complexity_id FROM complexity_levels 
        WHERE LOWER(TRIM(complexity_name)) = LOWER(TRIM(cua.complexity_to_fix))
        LIMIT 1
    ), 2) as complexity_id,
    
    -- Map usage_method text to usage_method_id
    COALESCE((
        SELECT usage_method_id FROM usage_methods 
        WHERE LOWER(TRIM(method_name)) = LOWER(TRIM(cua.usage_method))
        LIMIT 1
    ), 1) as usage_method_id,
    
    -- Map documentation_status text to doc_status_id
    COALESCE((
        SELECT doc_status_id FROM documentation_statuses 
        WHERE LOWER(TRIM(status_name)) = LOWER(TRIM(cua.documentation_status))
        LIMIT 1
    ), 1) as doc_status_id,
    
    -- Map testing_status text to test_status_id
    COALESCE((
        SELECT test_status_id FROM testing_statuses 
        WHERE LOWER(TRIM(status_name)) = LOWER(TRIM(cua.testing_status))
        LIMIT 1
    ), 1) as test_status_id,
    
    -- Map production_ready text to readiness_id
    COALESCE((
        SELECT readiness_id FROM readiness_statuses 
        WHERE (cua.production_ready = 'Yes' AND readiness_name = 'Yes')
           OR (cua.production_ready = 'No' AND readiness_name = 'No')  
           OR (cua.production_ready = 'Partial' AND readiness_name = 'Partial')
           OR (cua.production_ready = 'Unknown' AND readiness_name = 'Unknown')
        LIMIT 1
    ), 4) as readiness_id,
    
    cua.current_file_paths,
    cua.entry_points,
    cua.dependencies_on,
    cua.dependencies_from,
    cua.performance_impact,
    cua.created_at,
    cua.updated_at,
    cua.created_by,
    cua.is_active,
    cua.version
FROM component_usage_analysis cua;

SELECT 'Migration complete - Records migrated: ' || COUNT(*) as status FROM component_usage_analysis_v2;

-- =============================================================================
-- DATA VALIDATION AND INTEGRITY CHECKS
-- =============================================================================

SELECT 'PHASE 2 VALIDATION: Checking data integrity...' as status;

-- Check that all FK constraints are satisfied
SELECT 'Records with valid working_status_id: ' || COUNT(*) as validation
FROM component_usage_analysis_v2 cua_v2
JOIN working_statuses ws ON cua_v2.working_status_id = ws.working_status_id;

SELECT 'Records with valid priority_id: ' || COUNT(*) as validation
FROM component_usage_analysis_v2 cua_v2
JOIN priority_levels pl ON cua_v2.priority_id = pl.priority_id;

SELECT 'Records with valid complexity_id: ' || COUNT(*) as validation
FROM component_usage_analysis_v2 cua_v2
JOIN complexity_levels cl ON cua_v2.complexity_id = cl.complexity_id;

SELECT 'Records with valid usage_method_id: ' || COUNT(*) as validation
FROM component_usage_analysis_v2 cua_v2
JOIN usage_methods um ON cua_v2.usage_method_id = um.usage_method_id;

SELECT 'Records with valid doc_status_id: ' || COUNT(*) as validation
FROM component_usage_analysis_v2 cua_v2
JOIN documentation_statuses ds ON cua_v2.doc_status_id = ds.doc_status_id;

SELECT 'Records with valid test_status_id: ' || COUNT(*) as validation
FROM component_usage_analysis_v2 cua_v2
JOIN testing_statuses ts ON cua_v2.test_status_id = ts.test_status_id;

SELECT 'Records with valid readiness_id: ' || COUNT(*) as validation
FROM component_usage_analysis_v2 cua_v2
JOIN readiness_statuses rs ON cua_v2.readiness_id = rs.readiness_id;

-- Check for orphaned records
SELECT 'Records with invalid component_id: ' || COUNT(*) as validation
FROM component_usage_analysis_v2 cua_v2
LEFT JOIN components c ON cua_v2.component_id = c.component_id
WHERE c.component_id IS NULL;

-- Check foreign key constraints are working
PRAGMA foreign_key_check(component_usage_analysis_v2);

-- Compare record counts
SELECT 'Original component_usage_analysis records: ' || COUNT(*) as comparison
FROM component_usage_analysis;

SELECT 'New component_usage_analysis_v2 records: ' || COUNT(*) as comparison
FROM component_usage_analysis_v2;

-- Verify no NULL values in FK columns
SELECT 'Records with NULL FK values: ' || 
    SUM(CASE WHEN working_status_id IS NULL THEN 1 ELSE 0 END +
        CASE WHEN priority_id IS NULL THEN 1 ELSE 0 END +
        CASE WHEN complexity_id IS NULL THEN 1 ELSE 0 END +
        CASE WHEN usage_method_id IS NULL THEN 1 ELSE 0 END +
        CASE WHEN doc_status_id IS NULL THEN 1 ELSE 0 END +
        CASE WHEN test_status_id IS NULL THEN 1 ELSE 0 END +
        CASE WHEN readiness_id IS NULL THEN 1 ELSE 0 END) as validation
FROM component_usage_analysis_v2;

-- Show sample of migrated data for verification
SELECT 'Sample migrated data:' as sample;
SELECT 
    cua_v2.analysis_id,
    c.component_name,
    ws.status_name as working_status,
    pl.priority_name as priority,
    cl.complexity_name as complexity,
    um.method_name as usage_method,
    ds.status_name as doc_status,
    ts.status_name as test_status,
    rs.readiness_name as production_ready
FROM component_usage_analysis_v2 cua_v2
LEFT JOIN components c ON cua_v2.component_id = c.component_id
LEFT JOIN working_statuses ws ON cua_v2.working_status_id = ws.working_status_id
LEFT JOIN priority_levels pl ON cua_v2.priority_id = pl.priority_id
LEFT JOIN complexity_levels cl ON cua_v2.complexity_id = cl.complexity_id
LEFT JOIN usage_methods um ON cua_v2.usage_method_id = um.usage_method_id
LEFT JOIN documentation_statuses ds ON cua_v2.doc_status_id = ds.doc_status_id
LEFT JOIN testing_statuses ts ON cua_v2.test_status_id = ts.test_status_id
LEFT JOIN readiness_statuses rs ON cua_v2.readiness_id = rs.readiness_id
LIMIT 5;

SELECT 'PHASE 2 COMPLETE: Data migration and normalization successful!' as status;
SELECT 'Ready for Phase 3: Validation & sync setup' as next_step;
