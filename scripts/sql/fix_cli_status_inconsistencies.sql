-- Fix CLI Status Inconsistencies
-- Resolves mismatch between components and usage_analysis tables
-- Date: 2025-06-07 07:42:00

BEGIN TRANSACTION;

-- Update usage_analysis to match components status for CLI Entry Points
UPDATE component_usage_analysis 
SET 
    working_status = 'Fully Working',
    updated_at = CURRENT_TIMESTAMP
WHERE component_id = (SELECT component_id FROM components WHERE component_name = 'CLI Entry Points');

-- Update usage_analysis for CLI System
UPDATE component_usage_analysis 
SET 
    working_status = 'Partially Working',
    updated_at = CURRENT_TIMESTAMP
WHERE component_id = (SELECT component_id FROM components WHERE component_name = 'CLI System');

-- Update CLI Interface component (if it exists separately)
UPDATE components 
SET 
    status_id = 7,  -- Partially Working
    notes = 'CLI Interface working through fixed entry points. Core functionality operational.',
    updated_at = CURRENT_TIMESTAMP
WHERE component_name = 'CLI Interface';

-- Update usage_analysis for CLI Interface
UPDATE component_usage_analysis 
SET 
    working_status = 'Partially Working',
    updated_at = CURRENT_TIMESTAMP
WHERE component_id = (SELECT component_id FROM components WHERE component_name = 'CLI Interface');

-- Verify the fixes
SELECT 
    c.component_name,
    s.status_name as component_status,
    cua.working_status as usage_analysis_status,
    c.updated_at
FROM components c
JOIN statuses s ON c.status_id = s.status_id
LEFT JOIN component_usage_analysis cua ON c.component_id = cua.component_id
WHERE c.component_name LIKE '%CLI%'
ORDER BY c.component_name;

COMMIT;
