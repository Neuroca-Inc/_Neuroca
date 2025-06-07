-- Phase 2 Fix: Align lookup values with existing CHECK constraints
-- Date: 2025-06-07
-- Purpose: Update lookup tables to match existing constraint values

PRAGMA foreign_keys = ON;

SELECT 'PHASE 2 FIX: Aligning lookup values with existing constraints...' as status;

-- =============================================================================
-- UPDATE LOOKUP TABLES TO MATCH EXISTING CHECK CONSTRAINTS
-- =============================================================================

-- Clear and repopulate working_statuses to match existing constraint
DELETE FROM working_statuses;

INSERT INTO working_statuses (working_status_id, status_name, description, created_by) VALUES 
    (1, 'Unknown', 'Working status not determined', 'system:phase2_fix'),
    (2, 'Working', 'Component is fully operational', 'system:phase2_fix'),
    (3, 'Broken', 'Component has critical issues', 'system:phase2_fix'),
    (4, 'Partial', 'Some functionality works', 'system:phase2_fix'),
    (5, 'Not Tested', 'Component not yet tested', 'system:phase2_fix');

-- Clear and repopulate usage_methods to match common patterns
DELETE FROM usage_methods;

INSERT INTO usage_methods (usage_method_id, method_name, description, created_by) VALUES 
    (1, 'Method needs documentation', 'Usage method not documented', 'system:phase2_fix'),
    (2, 'Direct Import', 'Direct module import', 'system:phase2_fix'),
    (3, 'Factory Pattern', 'Created through factory', 'system:phase2_fix'),
    (4, 'Dependency Injection', 'Injected as dependency', 'system:phase2_fix'),
    (5, 'API Endpoint', 'Accessed via API', 'system:phase2_fix'),
    (6, 'CLI Command', 'Command line interface', 'system:phase2_fix'),
    (7, 'Event Handler', 'Event-driven usage', 'system:phase2_fix'),
    (8, 'Configuration', 'Configuration-based', 'system:phase2_fix');

-- Clear and repopulate documentation_statuses 
DELETE FROM documentation_statuses;

INSERT INTO documentation_statuses (doc_status_id, status_name, description, created_by) VALUES 
    (1, 'Needs documentation review', 'Documentation status unknown', 'system:phase2_fix'),
    (2, 'Not Documented', 'No documentation exists', 'system:phase2_fix'),
    (3, 'Partially Documented', 'Some documentation exists', 'system:phase2_fix'),
    (4, 'Fully Documented', 'Complete documentation', 'system:phase2_fix'),
    (5, 'Documentation Outdated', 'Documentation needs updating', 'system:phase2_fix');

-- Clear and repopulate testing_statuses
DELETE FROM testing_statuses;

INSERT INTO testing_statuses (test_status_id, status_name, description, created_by) VALUES 
    (1, 'Testing status needs assessment', 'Testing status unknown', 'system:phase2_fix'),
    (2, 'No Tests', 'No tests exist', 'system:phase2_fix'),
    (3, 'Unit Tests Only', 'Only unit tests exist', 'system:phase2_fix'),
    (4, 'Integration Tests', 'Integration tests exist', 'system:phase2_fix'),
    (5, 'Full Test Coverage', 'Comprehensive test coverage', 'system:phase2_fix'),
    (6, 'Tests Failing', 'Tests exist but failing', 'system:phase2_fix');

SELECT 'Lookup tables updated with correct constraint values' as status;

-- =============================================================================
-- CHECK WHAT DATA EXISTS IN HISTORY TO RESTORE FROM
-- =============================================================================

SELECT 'Checking available history data...' as status;

SELECT 'component_usage_analysis_history records: ' || COUNT(*) as available_data
FROM component_usage_analysis_history;

-- Show sample of available data
SELECT 'Sample of available working_status values in history:' as sample;
SELECT DISTINCT working_status, COUNT(*) as count
FROM component_usage_analysis_history 
WHERE working_status IS NOT NULL
GROUP BY working_status
ORDER BY count DESC;

-- Show sample priority values
SELECT 'Sample of available priority_to_fix values in history:' as sample;
SELECT DISTINCT priority_to_fix, COUNT(*) as count
FROM component_usage_analysis_history 
WHERE priority_to_fix IS NOT NULL
GROUP BY priority_to_fix
ORDER BY count DESC;

-- Show sample complexity values
SELECT 'Sample of available complexity_to_fix values in history:' as sample;
SELECT DISTINCT complexity_to_fix, COUNT(*) as count
FROM component_usage_analysis_history 
WHERE complexity_to_fix IS NOT NULL
GROUP BY complexity_to_fix
ORDER BY count DESC;

SELECT 'PHASE 2 FIX COMPLETE: Lookup tables aligned with existing constraints' as status;
