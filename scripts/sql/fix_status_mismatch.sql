-- Fix Status Mismatch Between Two Status Systems
-- Date: 2025-06-07
-- Purpose: Sync components.status_id with component_usage_analysis.working_status

PRAGMA foreign_keys = ON;

SELECT 'FIXING STATUS MISMATCH: Syncing two status systems...' as status;

-- Show current mismatches
SELECT 'CURRENT MISMATCHES:' as header;
SELECT 
    c.component_name,
    s.status_name as component_status,
    cua.working_status as usage_analysis_status
FROM components c 
JOIN statuses s ON c.status_id = s.status_id 
JOIN component_usage_analysis cua ON c.component_id = cua.component_id 
WHERE s.status_name != cua.working_status
ORDER BY c.component_name;

-- Update components.status_id to match working_status values
UPDATE components 
SET status_id = (
    SELECT s.status_id 
    FROM statuses s 
    WHERE s.status_name = (
        SELECT cua.working_status 
        FROM component_usage_analysis cua 
        WHERE cua.component_id = components.component_id
    )
)
WHERE EXISTS (
    SELECT 1 
    FROM component_usage_analysis cua 
    WHERE cua.component_id = components.component_id
);

SELECT 'Updated components.status_id to match working_status values' as status;

-- Show remaining mismatches (should be zero)
SELECT 'REMAINING MISMATCHES (should be zero):' as validation;
SELECT COUNT(*) as mismatch_count
FROM components c 
JOIN statuses s ON c.status_id = s.status_id 
JOIN component_usage_analysis cua ON c.component_id = cua.component_id 
WHERE s.status_name != cua.working_status;

-- Show final status distribution
SELECT 'FINAL STATUS DISTRIBUTION:' as final_check;
SELECT s.status_name, COUNT(*) as count
FROM components c 
JOIN statuses s ON c.status_id = s.status_id 
GROUP BY s.status_name
ORDER BY count DESC;

SELECT 'STATUS MISMATCH FIX COMPLETE!' as status;
