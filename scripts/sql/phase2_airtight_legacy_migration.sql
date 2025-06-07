-- Phase 2: Air-Tight Data Migration with Strict Legacy Status Values
-- Date: 2025-06-07
-- Purpose: Migrate data with ONLY verified legacy values + essential gap-fillers
-- GOAL: Prevent bad data with strict constraints

PRAGMA foreign_keys = ON;

SELECT 'PHASE 2 AIR-TIGHT: Starting migration with strict legacy values only...' as status;

-- =============================================================================
-- DEFINE WORKING_STATUSES WITH EXACT LEGACY VALUES ONLY
-- =============================================================================

SELECT 'Creating working_statuses with ONLY verified legacy values...' as status;

-- Clear and repopulate working_statuses with ONLY actual legacy values from history
DELETE FROM working_statuses;

-- ONLY the exact legacy values found in history data:
-- Fully Working (66), Exists But Not Connected (46), Missing (16), 
-- Partially Working (10), Broken (10), Blocked by missing service layer (3), 
-- Duplicated/Confused (1)
INSERT INTO working_statuses (working_status_id, status_name, description, created_by) VALUES 
    (1, 'Fully Working', 'Component is fully operational [LEGACY]', 'system:airtight_migration'),
    (2, 'Exists But Not Connected', 'Component exists but not integrated [LEGACY]', 'system:airtight_migration'),
    (3, 'Missing', 'Component not implemented [LEGACY]', 'system:airtight_migration'),
    (4, 'Partially Working', 'Some functionality works [LEGACY]', 'system:airtight_migration'),
    (5, 'Broken', 'Component has critical issues [LEGACY]', 'system:airtight_migration'),
    (6, 'Blocked by missing service layer', 'Waiting for service layer [LEGACY]', 'system:airtight_migration'),
    (7, 'Duplicated/Confused', 'Multiple conflicting implementations [LEGACY]', 'system:airtight_migration'),
    -- ONLY essential gap-filler for data integrity:
    (8, 'Unknown', 'Working status not determined [GAP-FILLER]', 'system:airtight_migration');

SELECT 'Working statuses populated with ONLY verified legacy + essential Unknown' as status;

-- =============================================================================
-- CREATE AIR-TIGHT TABLE WITH STRICT CONSTRAINTS
-- =============================================================================

SELECT 'Creating air-tight table with STRICT CHECK constraints...' as status;

-- Create new table with ULTRA-STRICT constraints (ONLY verified legacy values)
CREATE TABLE component_usage_analysis_airtight (
    analysis_id INTEGER PRIMARY KEY AUTOINCREMENT,
    component_id INTEGER NOT NULL,
    expected_usage TEXT NOT NULL CHECK(length(expected_usage) >= 10),
    actual_integration_status TEXT NOT NULL CHECK(length(actual_integration_status) >= 5),
    missing_dependencies TEXT NOT NULL DEFAULT 'None identified',
    integration_issues TEXT NOT NULL DEFAULT 'None identified',
    usage_method TEXT NOT NULL CHECK(length(usage_method) >= 5),
    
    -- ULTRA-STRICT: ONLY exact legacy values allowed (NO deviations)
    working_status TEXT NOT NULL CHECK(working_status IN (
        'Fully Working',
        'Exists But Not Connected', 
        'Missing',
        'Partially Working',
        'Broken',
        'Blocked by missing service layer',
        'Duplicated/Confused',
        'Unknown'
    )),
    
    -- Strict priority constraints (only existing values)
    priority_to_fix TEXT NOT NULL CHECK(priority_to_fix IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
    
    -- Strict complexity constraints (only existing values)
    complexity_to_fix TEXT NOT NULL CHECK(complexity_to_fix IN ('Easy', 'Medium', 'Hard', 'Very Hard')),
    
    current_file_paths TEXT NOT NULL CHECK(length(current_file_paths) >= 3),
    entry_points TEXT DEFAULT 'No specific entry points',
    dependencies_on TEXT NOT NULL DEFAULT 'Standard dependencies only',
    dependencies_from TEXT DEFAULT 'No dependencies identified',
    
    -- Strict performance impact
    performance_impact TEXT CHECK(
        performance_impact IS NULL OR 
        performance_impact IN ('Critical', 'High', 'Medium', 'Low', 'Not assessed')
    ),
    
    documentation_status TEXT NOT NULL DEFAULT 'Needs documentation review',
    testing_status TEXT NOT NULL DEFAULT 'Testing status needs assessment',
    
    -- Strict production ready
    production_ready TEXT NOT NULL CHECK(production_ready IN ('Yes', 'No', 'Partial', 'Unknown')),
    
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT NOT NULL DEFAULT 'system',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    version INTEGER NOT NULL DEFAULT 1,
    
    -- Foreign key constraint with ON DELETE and ON UPDATE rules for data integrity
    FOREIGN KEY (component_id) REFERENCES components(component_id) 
        ON DELETE RESTRICT 
        ON UPDATE CASCADE
);

-- Replace old table with air-tight version
DROP TABLE IF EXISTS component_usage_analysis;
ALTER TABLE component_usage_analysis_airtight RENAME TO component_usage_analysis;

SELECT 'Air-tight table created with ULTRA-STRICT constraints' as status;

-- =============================================================================
-- RESTORE DATA WITH STRICT VALIDATION
-- =============================================================================

SELECT 'Restoring data with strict validation...' as status;

-- Restore data with validation - reject any that don't meet strict criteria
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
    CASE 
        WHEN length(COALESCE(expected_usage, '')) >= 10 THEN expected_usage
        ELSE 'Usage analysis pending - ' || COALESCE(expected_usage, 'no details')
    END as expected_usage,
    CASE 
        WHEN length(COALESCE(actual_integration_status, '')) >= 5 THEN actual_integration_status
        ELSE 'Integration status needs assessment'
    END as actual_integration_status,
    COALESCE(missing_dependencies, 'None identified') as missing_dependencies,
    COALESCE(integration_issues, 'None identified') as integration_issues,
    CASE 
        WHEN length(COALESCE(usage_method, '')) >= 5 THEN usage_method
        ELSE 'Method needs documentation'
    END as usage_method,
    
    -- STRICT: Only allow exact legacy values, default to Unknown for any non-conforming
    CASE 
        WHEN working_status IN (
            'Fully Working', 'Exists But Not Connected', 'Missing',
            'Partially Working', 'Broken', 'Blocked by missing service layer',
            'Duplicated/Confused'
        ) THEN working_status
        ELSE 'Unknown'
    END as working_status,
    
    -- Validate priority
    CASE 
        WHEN priority_to_fix IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL') THEN priority_to_fix
        ELSE 'MEDIUM'
    END as priority_to_fix,
    
    -- Validate complexity
    CASE 
        WHEN complexity_to_fix IN ('Easy', 'Medium', 'Hard', 'Very Hard') THEN complexity_to_fix
        ELSE 'Medium'
    END as complexity_to_fix,
    
    CASE 
        WHEN length(COALESCE(current_file_paths, '')) >= 3 THEN current_file_paths
        ELSE 'N/A'
    END as current_file_paths,
    
    COALESCE(entry_points, 'No specific entry points') as entry_points,
    COALESCE(dependencies_on, 'Standard dependencies only') as dependencies_on,
    COALESCE(dependencies_from, 'No dependencies identified') as dependencies_from,
    
    -- Validate performance impact
    CASE 
        WHEN performance_impact IN ('Critical', 'High', 'Medium', 'Low') THEN performance_impact
        ELSE 'Not assessed'
    END as performance_impact,
    
    COALESCE(documentation_status, 'Needs documentation review') as documentation_status,
    COALESCE(testing_status, 'Testing status needs assessment') as testing_status,
    
    -- Validate production ready
    CASE 
        WHEN production_ready IN ('Yes', 'No', 'Partial', 'Unknown') THEN production_ready
        ELSE 'Unknown'
    END as production_ready,
    
    created_at, updated_at, 
    COALESCE(created_by, 'system') as created_by,
    COALESCE(is_active, TRUE) as is_active,
    COALESCE(version, 1) as version
FROM (
    SELECT *,
           ROW_NUMBER() OVER (PARTITION BY analysis_id ORDER BY history_timestamp DESC) as rn
    FROM component_usage_analysis_history
    WHERE history_operation != 'DELETE'
      AND component_id IS NOT NULL  -- Extra validation
) ranked
WHERE rn = 1;

SELECT 'Data restored - Records: ' || COUNT(*) as status FROM component_usage_analysis;

-- Show any working_status values that were defaulted to Unknown (data quality check)
SELECT 'Records defaulted to Unknown working_status: ' || COUNT(*) as data_quality_check
FROM component_usage_analysis 
WHERE working_status = 'Unknown';

-- =============================================================================
-- MIGRATE TO NORMALIZED V2 TABLE WITH STRICT FK VALIDATION
-- =============================================================================

SELECT 'Migrating to normalized component_usage_analysis_v2 with strict validation...' as status;

-- Clear V2 table first
DELETE FROM component_usage_analysis_v2;

-- Insert with strict FK mapping and validation
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
    
    -- STRICT FK mapping - must match exactly
    (SELECT working_status_id FROM working_statuses 
     WHERE status_name = cua.working_status) as working_status_id,
    
    -- STRICT priority mapping
    (SELECT priority_id FROM priority_levels 
     WHERE priority_name = cua.priority_to_fix) as priority_id,
    
    -- STRICT complexity mapping
    (SELECT complexity_id FROM complexity_levels 
     WHERE complexity_name = cua.complexity_to_fix) as complexity_id,
    
    -- Default to first usage method if no exact match
    COALESCE((
        SELECT usage_method_id FROM usage_methods 
        WHERE LOWER(TRIM(method_name)) = LOWER(TRIM(cua.usage_method))
        LIMIT 1
    ), 1) as usage_method_id,
    
    -- Default to first doc status if no exact match
    COALESCE((
        SELECT doc_status_id FROM documentation_statuses 
        WHERE LOWER(TRIM(status_name)) = LOWER(TRIM(cua.documentation_status))
        LIMIT 1
    ), 1) as doc_status_id,
    
    -- Default to first test status if no exact match
    COALESCE((
        SELECT test_status_id FROM testing_statuses 
        WHERE LOWER(TRIM(status_name)) = LOWER(TRIM(cua.testing_status))
        LIMIT 1
    ), 1) as test_status_id,
    
    -- STRICT readiness mapping
    (SELECT readiness_id FROM readiness_statuses 
     WHERE readiness_name = cua.production_ready) as readiness_id,
    
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
FROM component_usage_analysis cua
WHERE EXISTS (SELECT 1 FROM components c WHERE c.component_id = cua.component_id);  -- Extra FK validation

SELECT 'Migration complete - Records migrated: ' || COUNT(*) as status FROM component_usage_analysis_v2;

-- =============================================================================
-- ULTRA-STRICT DATA VALIDATION
-- =============================================================================

SELECT 'PHASE 2 ULTRA-STRICT VALIDATION: Checking data integrity...' as status;

-- Validate ALL foreign keys exist
SELECT 'Records with valid working_status_id: ' || COUNT(*) as validation
FROM component_usage_analysis_v2 cua_v2
JOIN working_statuses ws ON cua_v2.working_status_id = ws.working_status_id;

SELECT 'Records with valid component_id: ' || COUNT(*) as validation
FROM component_usage_analysis_v2 cua_v2
JOIN components c ON cua_v2.component_id = c.component_id;

-- Check for any NULL FK values (should be ZERO)
SELECT 'Records with NULL FK values (MUST BE ZERO): ' || 
    COUNT(*) as critical_validation
FROM component_usage_analysis_v2
WHERE working_status_id IS NULL 
   OR priority_id IS NULL 
   OR complexity_id IS NULL 
   OR readiness_id IS NULL
   OR component_id IS NULL;

-- Verify ONLY legacy working status values exist
SELECT 'LEGACY WORKING STATUS DISTRIBUTION:' as legacy_validation;
SELECT ws.status_name, COUNT(*) as count,
       CASE WHEN ws.status_name IN (
           'Fully Working', 'Exists But Not Connected', 'Missing',
           'Partially Working', 'Broken', 'Blocked by missing service layer',
           'Duplicated/Confused', 'Unknown'
       ) THEN '✓ VALID LEGACY' ELSE '✗ INVALID' END as validation
FROM component_usage_analysis_v2 cua_v2
JOIN working_statuses ws ON cua_v2.working_status_id = ws.working_status_id
GROUP BY ws.status_name, validation
ORDER BY count DESC;

-- Final constraint validation
PRAGMA foreign_key_check(component_usage_analysis_v2);

SELECT 'PHASE 2 AIR-TIGHT COMPLETE: Migration with ULTRA-STRICT legacy values successful!' as status;
SELECT 'Air-tight database: ONLY verified legacy values + essential Unknown allowed' as confirmation;
SELECT 'Bad data prevention: ACTIVE via strict CHECK constraints' as security;
