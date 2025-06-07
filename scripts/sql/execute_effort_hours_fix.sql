-- Execute effort hours fix for verified "Fully Working" components
-- Based on manual review of 22 flagged components on 2025-06-07

BEGIN TRANSACTION;

-- Create a backup log of changes before making them
CREATE TEMP TABLE effort_hours_fixes AS
SELECT 
    c.component_id,
    c.component_name,
    s.status_name,
    c.effort_hours as old_effort_hours,
    0 as new_effort_hours,
    datetime('now') as fix_timestamp
FROM components c
JOIN statuses s ON c.status_id = s.status_id
WHERE c.is_active = TRUE
  AND s.status_name = 'Fully Working' 
  AND c.effort_hours > 0;

-- Show what will be changed
SELECT 'Components to fix:' as action, COUNT(*) as count FROM effort_hours_fixes;
SELECT component_name, old_effort_hours FROM effort_hours_fixes ORDER BY old_effort_hours DESC;

-- Apply the fix (ACTIVE VERSION - executing the update)
UPDATE components 
SET effort_hours = 0,
    updated_at = datetime('now'),
    notes = CASE 
        WHEN notes IS NULL OR notes = '' THEN 'Auto-fixed: Set effort_hours to 0 for Fully Working component (Manual review verified 2025-06-07)'
        ELSE notes || ' | Auto-fixed: Set effort_hours to 0 for Fully Working component (Manual review verified 2025-06-07)'
    END
WHERE component_id IN (SELECT component_id FROM effort_hours_fixes);

-- Log the fixes for audit trail
INSERT INTO component_issues (component_id, issue_description, severity, resolved, created_by, resolved_by)
SELECT 
    component_id,
    'Auto-fix applied: effort_hours set to 0 for Fully Working component (was ' || old_effort_hours || 'h) - Manual review verified',
    'INFO',
    TRUE,
    'automated_fix_script',
    'manual_review_verified'
FROM effort_hours_fixes;

-- Show results after fix
SELECT 'Fix applied. Results:' as status, COUNT(*) as components_updated FROM effort_hours_fixes;

COMMIT;
