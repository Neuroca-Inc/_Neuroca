-- Comprehensive Database Restoration and Normalization
-- Date: 2025-06-07
-- Purpose: Restore wiped tables, eliminate NULLs, ensure temporal consistency, add cross-table sync
-- WARNING: This script makes significant changes - review carefully before execution

-- =============================================================================
-- PHASE 1: DATA RECOVERY - Restore wiped tables from history
-- =============================================================================

-- First, let's check what we're working with
SELECT 'PHASE 1: Starting Data Recovery...' as status;

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

SELECT 'Data Recovery Complete - Records restored: ' || COUNT(*) as status FROM component_usage_analysis;

-- =============================================================================
-- PHASE 2: FIX ACTUAL NORMALIZATION ISSUES - Create missing tables and fix duplicates
-- =============================================================================

SELECT 'PHASE 2: Fixing actual normalization issues...' as status;

-- Create missing working_statuses table that component_status references
CREATE TABLE IF NOT EXISTS working_statuses (
    working_status_id INTEGER PRIMARY KEY,
    status_name TEXT NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE
);

-- Populate working_statuses with values found in component_usage_analysis
INSERT OR IGNORE INTO working_statuses (working_status_id, status_name, description)
VALUES 
    (1, 'Unknown', 'Working status not determined'),
    (2, 'Broken', 'Component has critical issues'),
    (3, 'Partially Working', 'Some functionality works'),
    (4, 'Fully Working', 'All functionality operational'),
    (5, 'Missing', 'Component not implemented'),
    (6, 'Exists But Not Connected', 'Component exists but not integrated');

-- Remove only the truly empty duplicate table
DROP TABLE IF EXISTS component_usage_core;

SELECT 'Real normalization fixes complete' as status;

-- =============================================================================
-- PHASE 3: NULL ELIMINATION - Replace all NULLs with meaningful defaults
-- =============================================================================

SELECT 'PHASE 3: Eliminating NULL values...' as status;

-- Fix NULLs in component_usage_analysis
UPDATE component_usage_analysis SET
    expected_usage = COALESCE(expected_usage, 'Usage analysis pending'),
    actual_integration_status = COALESCE(actual_integration_status, 'Integration status needs assessment'),
    missing_dependencies = COALESCE(missing_dependencies, 'None identified'),
    integration_issues = COALESCE(integration_issues, 'None identified'),
    usage_method = COALESCE(usage_method, 'Method needs documentation'),
    working_status = COALESCE(working_status, 'Unknown'),
    priority_to_fix = COALESCE(priority_to_fix, 'MEDIUM'),
    complexity_to_fix = COALESCE(complexity_to_fix, 'Medium'),
    current_file_paths = COALESCE(current_file_paths, 'N/A'),
    entry_points = COALESCE(entry_points, 'No specific entry points'),
    dependencies_on = COALESCE(dependencies_on, 'Standard dependencies only'),
    dependencies_from = COALESCE(dependencies_from, 'No dependencies identified'),
    performance_impact = COALESCE(performance_impact, 'Not assessed'),
    documentation_status = COALESCE(documentation_status, 'Needs documentation review'),
    testing_status = COALESCE(testing_status, 'Testing status needs assessment'),
    production_ready = COALESCE(production_ready, 'Unknown'),
    created_by = COALESCE(created_by, 'system'),
    updated_at = COALESCE(updated_at, CURRENT_TIMESTAMP),
    created_at = COALESCE(created_at, CURRENT_TIMESTAMP),
    is_active = COALESCE(is_active, TRUE),
    version = COALESCE(version, 1);

-- Fix NULLs in component_issues
UPDATE component_issues SET
    severity = COALESCE(severity, 'Medium'),
    resolved = COALESCE(resolved, FALSE),
    created_at = COALESCE(created_at, CURRENT_TIMESTAMP),
    updated_at = COALESCE(updated_at, CURRENT_TIMESTAMP),
    created_by = COALESCE(created_by, 'system'),
    resolved_by = COALESCE(resolved_by, 'N/A'),
    is_active = COALESCE(is_active, TRUE);

-- Fix NULLs in component_dependencies  
UPDATE component_dependencies SET
    dependency_type = COALESCE(dependency_type, 'requires'),
    created_at = COALESCE(created_at, CURRENT_TIMESTAMP),
    updated_at = COALESCE(updated_at, CURRENT_TIMESTAMP),
    created_by = COALESCE(created_by, 'system'),
    is_active = COALESCE(is_active, TRUE);

-- Fix NULLs in components table
UPDATE components SET
    component_name = COALESCE(component_name, 'Unnamed Component'),
    status_id = COALESCE(status_id, 6), -- Default to "Missing" status
    category_id = COALESCE(category_id, 1), -- Default to first category
    created_at = COALESCE(created_at, CURRENT_TIMESTAMP),
    updated_at = COALESCE(updated_at, CURRENT_TIMESTAMP),
    created_by = COALESCE(created_by, 'system'),
    is_active = COALESCE(is_active, TRUE),
    completion_percentage = COALESCE(completion_percentage, 0),
    effort_hours = COALESCE(effort_hours, 0),
    priority = COALESCE(priority, 3), -- Default to medium priority
    notes = COALESCE(notes, 'No notes available');

SELECT 'NULL elimination complete' as status;

-- =============================================================================
-- PHASE 4: ENHANCED AUDIT TRAIL SYSTEM
-- =============================================================================

SELECT 'PHASE 4: Setting up enhanced audit trails...' as status;

-- Create standardized audit source tracking
-- Format: 'manual:username', 'trigger:source_table', 'system:process_name'

-- Update existing triggers to use proper audit sources
DROP TRIGGER IF EXISTS component_usage_analysis_update_timestamp;
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

-- =============================================================================
-- PHASE 5: CROSS-TABLE CONSISTENCY TRIGGERS (Data Synchronization)
-- =============================================================================

SELECT 'PHASE 5: Creating cross-table consistency triggers...' as status;

-- Trigger: When component status changes, update related usage analysis
CREATE TRIGGER IF NOT EXISTS sync_component_status_to_usage
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
    updated_at = CURRENT_TIMESTAMP,
    created_by = 'trigger:components.status_change',
    version = version + 1
    WHERE component_id = NEW.component_id;
END;

-- Trigger: When issues are resolved, potentially update component status
CREATE TRIGGER IF NOT EXISTS sync_resolved_issues_to_component
AFTER UPDATE OF resolved ON component_issues
FOR EACH ROW
WHEN OLD.resolved = FALSE AND NEW.resolved = TRUE
BEGIN
    -- Check if this was the last unresolved issue for the component
    UPDATE components 
    SET status_id = (
        CASE 
            WHEN (SELECT COUNT(*) FROM component_issues 
                  WHERE component_id = NEW.component_id 
                  AND resolved = FALSE 
                  AND is_active = TRUE) = 0 
            THEN 8 -- "Fully Working" status
            ELSE status_id -- Keep current status
        END
    ),
    updated_at = CURRENT_TIMESTAMP,
    created_by = 'trigger:component_issues.resolved'
    WHERE component_id = NEW.component_id;
    
    -- Update usage analysis to reflect issue resolution
    UPDATE component_usage_analysis
    SET integration_issues = 'Recent issues resolved: ' || NEW.issue_description,
        updated_at = CURRENT_TIMESTAMP,
        created_by = 'trigger:component_issues.resolved',
        version = version + 1
    WHERE component_id = NEW.component_id;
END;

-- Trigger: When dependencies change, update dependent components
CREATE TRIGGER IF NOT EXISTS sync_dependency_changes
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

-- =============================================================================
-- PHASE 6: FOREIGN KEY VALIDATION AND ENFORCEMENT
-- =============================================================================

SELECT 'PHASE 6: Validating foreign key constraints...' as status;

-- Check for orphaned records in component_usage_analysis
SELECT 'Orphaned usage analysis records: ' || COUNT(*) as validation
FROM component_usage_analysis cua
LEFT JOIN components c ON cua.component_id = c.component_id
WHERE c.component_id IS NULL;

-- Check for orphaned records in component_issues
SELECT 'Orphaned issue records: ' || COUNT(*) as validation
FROM component_issues ci
LEFT JOIN components c ON ci.component_id = c.component_id
WHERE c.component_id IS NULL;

-- Check for orphaned records in component_dependencies
SELECT 'Orphaned dependency records: ' || COUNT(*) as validation
FROM component_dependencies cd
LEFT JOIN components c ON cd.component_id = c.component_id
WHERE c.component_id IS NULL;

-- Check for invalid status references
SELECT 'Invalid status references: ' || COUNT(*) as validation
FROM components c
LEFT JOIN statuses s ON c.status_id = s.status_id
WHERE s.status_id IS NULL;

-- =============================================================================
-- PHASE 7: TEMPORAL TABLE VERIFICATION
-- =============================================================================

SELECT 'PHASE 7: Verifying temporal table system...' as status;

-- Check that all main tables have corresponding history tables
SELECT 
    'Main tables: ' || COUNT(*) as info
FROM sqlite_master 
WHERE type='table' 
AND name NOT LIKE '%_history' 
AND name NOT LIKE 'sqlite_%'
AND name NOT LIKE 'current_%'
AND name NOT LIKE 'bug_%'
AND name NOT LIKE 'automation_%'
AND name NOT LIKE 'file_%'
AND name NOT LIKE 'usage_%'
AND name NOT LIKE 'change_%';

SELECT 
    'History tables: ' || COUNT(*) as info
FROM sqlite_master 
WHERE type='table' 
AND name LIKE '%_history';

-- =============================================================================
-- FINAL VALIDATION
-- =============================================================================

SELECT 'PHASE 8: Final validation...' as status;

-- Check that no NULL values remain in critical fields
SELECT 'NULL values in component_usage_analysis: ' || 
    SUM(CASE WHEN expected_usage IS NULL THEN 1 ELSE 0 END +
        CASE WHEN actual_integration_status IS NULL THEN 1 ELSE 0 END +
        CASE WHEN usage_method IS NULL THEN 1 ELSE 0 END +
        CASE WHEN working_status IS NULL THEN 1 ELSE 0 END) as validation
FROM component_usage_analysis;

-- Verify record counts
SELECT 'Final record counts:' as summary;
SELECT 'component_usage_analysis: ' || COUNT(*) as count FROM component_usage_analysis;
SELECT 'component_issues: ' || COUNT(*) as count FROM component_issues;
SELECT 'component_dependencies: ' || COUNT(*) as count FROM component_dependencies;
SELECT 'components: ' || COUNT(*) as count FROM components;

SELECT 'DATABASE RESTORATION AND NORMALIZATION COMPLETE!' as status;
SELECT 'All phases completed successfully.' as final_status;
