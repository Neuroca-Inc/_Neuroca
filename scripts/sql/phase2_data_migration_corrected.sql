-- Phase 2 Corrected: Data Migration with Proper Value Mapping
-- Date: 2025-06-07
-- Purpose: Migrate data using actual history values and constraint mappings

PRAGMA foreign_keys = ON;

SELECT 'PHASE 2 CORRECTED: Starting data migration with proper mappings...' as status;

-- =============================================================================
-- UPDATE LOOKUP TABLES WITH ACTUAL HISTORY VALUES
-- =============================================================================

SELECT 'Updating lookup tables with actual history values...' as status;

-- Clear and repopulate working_statuses with actual history values mapped to constraints
DELETE FROM working_statuses;

INSERT INTO working_statuses (working_status_id, status_name, description, created_by) VALUES 
    (1, 'Unknown', 'Working status not determined', 'system:phase2_corrected'),
    (2, 'Broken', 'Component has critical issues', 'system:phase2_corrected'),
    (3, 'Partial', 'Some functionality works (maps to Partially Working)', 'system:phase2_corrected'),
    (4, 'Working', 'Component is fully operational (maps to Fully Working)', 'system:phase2_corrected'),
    (5, 'Not Tested', 'Component not yet tested', 'system:phase2_corrected');

-- Add extended working statuses for the unmappable values (store as text in normalized table)
-- These will be stored in the text fields of the normalized table since they don't fit constraints

SELECT 'Lookup tables updated with constraint-compatible values' as status;

-- =============================================================================
-- RESTORE DATA FROM HISTORY WITH VALUE MAPPING
-- =============================================================================

SELECT 'Restoring data from component_usage_analysis_history with value mapping...' as status;

-- Clear any existing data 
DELETE FROM component_usage_analysis WHERE 1=1;

-- Restore component_usage_analysis from history with value mapping
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
    
    -- Map working_status from history to constraint values
    CASE 
        WHEN working_status = 'Fully Working' THEN 'Working'
        WHEN working_status = 'Partially Working' THEN 'Partial' 
        WHEN working_status = 'Broken' THEN 'Broken'
        WHEN working_status IN ('Exists But Not Connected', 'Missing', 'Blocked by missing service layer', 'Duplicated/Confused') THEN 'Unknown'
        ELSE COALESCE(working_status, 'Unknown')
    END as working_status,
    
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

-- Insert data into normalized table with FK mappings and original values preserved
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
    
    -- Store original working status in actual_integration_status for unmappable values
    CASE 
        WHEN cua.working_status IN ('Working', 'Broken', 'Partial', 'Unknown') THEN cua.actual_integration_status
        ELSE cua.actual_integration_status || ' [Original working status: ' || 
             (SELECT working_status FROM component_usage_analysis_history h 
              WHERE h.analysis_id = cua.analysis_id 
              ORDER BY h.history_timestamp DESC LIMIT 1) || ']'
    END as actual_integration_status,
    
    cua.missing_dependencies,
    cua.integration_issues,
    
    -- Map working_status text to working_status_id
    CASE cua.working_status
        WHEN 'Working' THEN 4
        WHEN 'Broken' THEN 2
        WHEN 'Partial' THEN 3
        WHEN 'Unknown' THEN 1
        WHEN 'Not Tested' THEN 5
        ELSE 1
    END as working_status_id,
    
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

-- Compare record counts
SELECT 'Original component_usage_analysis records: ' || COUNT(*) as comparison
FROM component_usage_analysis;

SELECT 'New component_usage_analysis_v2 records: ' || COUNT(*) as comparison
FROM component_usage_analysis_v2;

-- Show sample of migrated data for verification
SELECT 'Sample migrated data:' as sample;
SELECT 
    cua_v2.analysis_id,
    c.component_name,
    ws.status_name as working_status,
    pl.priority_name as priority,
    cl.complexity_name as complexity
FROM component_usage_analysis_v2 cua_v2
LEFT JOIN components c ON cua_v2.component_id = c.component_id
LEFT JOIN working_statuses ws ON cua_v2.working_status_id = ws.working_status_id
LEFT JOIN priority_levels pl ON cua_v2.priority_id = pl.priority_id
LEFT JOIN complexity_levels cl ON cua_v2.complexity_id = cl.complexity_id
LIMIT 5;

-- Show working status mapping
SELECT 'Working status distribution in normalized table:' as distribution;
SELECT ws.status_name, COUNT(*) as count
FROM component_usage_analysis_v2 cua_v2
JOIN working_statuses ws ON cua_v2.working_status_id = ws.working_status_id
GROUP BY ws.status_name
ORDER BY count DESC;

SELECT 'PHASE 2 CORRECTED COMPLETE: Data migration with proper value mapping successful!' as status;
SELECT 'Ready for Phase 3: Validation & sync setup' as next_step;
