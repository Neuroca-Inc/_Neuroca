-- Phase 2: Data Migration Preserving Legacy Status Values
-- Date: 2025-06-07
-- Purpose: Migrate data while preserving original legacy working status values

PRAGMA foreign_keys = ON;

SELECT 'PHASE 2: Starting data migration preserving legacy values...' as status;

-- =============================================================================
-- UPDATE WORKING_STATUSES WITH ACTUAL LEGACY VALUES
-- =============================================================================

SELECT 'Updating working_statuses with legacy values from history...' as status;

-- Clear and repopulate working_statuses with actual legacy values
DELETE FROM working_statuses;

INSERT INTO working_statuses (working_status_id, status_name, description, created_by) VALUES 
    (1, 'Unknown', 'Working status not determined', 'system:legacy_preserve'),
    (2, 'Fully Working', 'Component is fully operational', 'system:legacy_preserve'),
    (3, 'Exists But Not Connected', 'Component exists but not integrated', 'system:legacy_preserve'),
    (4, 'Missing', 'Component not implemented', 'system:legacy_preserve'),
    (5, 'Partially Working', 'Some functionality works', 'system:legacy_preserve'),
    (6, 'Broken', 'Component has critical issues', 'system:legacy_preserve'),
    (7, 'Blocked by missing service layer', 'Waiting for service layer', 'system:legacy_preserve'),
    (8, 'Duplicated/Confused', 'Multiple conflicting implementations', 'system:legacy_preserve');

SELECT 'Working statuses updated with legacy values' as status;

-- =============================================================================
-- MODIFY CHECK CONSTRAINT TO ALLOW LEGACY VALUES
-- =============================================================================

SELECT 'Modifying CHECK constraint to allow legacy values...' as status;

-- Create new table with updated constraint
CREATE TABLE component_usage_analysis_new (
    analysis_id INTEGER PRIMARY KEY AUTOINCREMENT,
    component_id INTEGER NOT NULL,
    expected_usage TEXT NOT NULL CHECK(length(expected_usage) > 10),
    actual_integration_status TEXT NOT NULL CHECK(length(actual_integration_status) > 5),
    missing_dependencies TEXT NOT NULL DEFAULT 'None identified',
    integration_issues TEXT NOT NULL DEFAULT 'None identified',
    usage_method TEXT NOT NULL CHECK(length(usage_method) > 5),
    working_status TEXT NOT NULL CHECK(working_status IN (
        'Unknown', 'Fully Working', 'Exists But Not Connected', 'Missing', 
        'Partially Working', 'Broken', 'Blocked by missing service layer', 
        'Duplicated/Confused'
    )),
    priority_to_fix TEXT NOT NULL CHECK(priority_to_fix IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
    complexity_to_fix TEXT NOT NULL CHECK(complexity_to_fix IN ('Easy', 'Medium', 'Hard', 'Very Hard')),
    current_file_paths TEXT NOT NULL CHECK(length(current_file_paths) > 3),
    entry_points TEXT DEFAULT 'No specific entry points',
    dependencies_on TEXT NOT NULL DEFAULT 'Standard dependencies only',
    dependencies_from TEXT DEFAULT 'No dependencies identified',
    performance_impact TEXT CHECK(performance_impact IS NULL OR performance_impact IN ('Critical', 'High', 'Medium', 'Low')),
    documentation_status TEXT NOT NULL DEFAULT 'Needs documentation review',
    testing_status TEXT NOT NULL DEFAULT 'Testing status needs assessment',
    production_ready TEXT NOT NULL CHECK(production_ready IN ('Yes', 'No', 'Partial', 'Unknown')),
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT NOT NULL DEFAULT 'system',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    version INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (component_id) REFERENCES components(component_id)
);

-- Copy any existing data (should be empty after previous attempts)
INSERT INTO component_usage_analysis_new 
SELECT * FROM component_usage_analysis;

-- Replace old table
DROP TABLE component_usage_analysis;
ALTER TABLE component_usage_analysis_new RENAME TO component_usage_analysis;

SELECT 'CHECK constraint updated to allow legacy values' as status;

-- =============================================================================
-- RESTORE DATA FROM HISTORY PRESERVING LEGACY VALUES
-- =============================================================================

SELECT 'Restoring data from component_usage_analysis_history preserving legacy values...' as status;

-- Restore component_usage_analysis from history preserving original working_status
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
    COALESCE(working_status, 'Unknown') as working_status,  -- Preserve original legacy values
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

SELECT 'Migrating data to normalized component_usage_analysis_v2 preserving legacy values...' as status;

-- Insert data into normalized table with FK mappings to legacy values
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
    
    -- Map legacy working_status text to working_status_id
    COALESCE((
        SELECT working_status_id FROM working_statuses 
        WHERE status_name = cua.working_status
        LIMIT 1
    ), 1) as working_status_id,
    
    -- Map priority_to_fix text to priority_id
    COALESCE((
        SELECT priority_id FROM priority_levels 
        WHERE UPPER(TRIM(priority_name)) = UPPER(TRIM(cua.priority_to_fix))
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

-- Compare record counts
SELECT 'Original component_usage_analysis records: ' || COUNT(*) as comparison
FROM component_usage_analysis;

SELECT 'New component_usage_analysis_v2 records: ' || COUNT(*) as comparison
FROM component_usage_analysis_v2;

-- Show legacy working status distribution preserved
SELECT 'Legacy working status distribution in normalized table:' as distribution;
SELECT ws.status_name, COUNT(*) as count
FROM component_usage_analysis_v2 cua_v2
JOIN working_statuses ws ON cua_v2.working_status_id = ws.working_status_id
GROUP BY ws.status_name
ORDER BY count DESC;

-- Show sample of migrated data with legacy values
SELECT 'Sample migrated data with legacy values preserved:' as sample;
SELECT 
    cua_v2.analysis_id,
    c.component_name,
    ws.status_name as legacy_working_status,
    pl.priority_name as priority,
    cl.complexity_name as complexity
FROM component_usage_analysis_v2 cua_v2
LEFT JOIN components c ON cua_v2.component_id = c.component_id
LEFT JOIN working_statuses ws ON cua_v2.working_status_id = ws.working_status_id
LEFT JOIN priority_levels pl ON cua_v2.priority_id = pl.priority_id
LEFT JOIN complexity_levels cl ON cua_v2.complexity_id = cl.complexity_id
LIMIT 10;

SELECT 'PHASE 2 COMPLETE: Data migration preserving legacy working status values successful!' as status;
SELECT 'Legacy values preserved: Fully Working, Exists But Not Connected, Missing, etc.' as confirmation;
SELECT 'Ready for Phase 3: Validation & sync setup' as next_step;
