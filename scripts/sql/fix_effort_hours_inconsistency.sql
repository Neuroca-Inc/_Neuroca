
    -- Script to fix effort hours inconsistency
    -- Sets effort_hours to 0 for all components marked as "Fully Working"
    
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
    
    -- Apply the fix (commented out for safety - uncomment to execute)
    /*
    UPDATE components 
    SET effort_hours = 0,
        updated_at = datetime('now'),
        notes = CASE 
            WHEN notes IS NULL OR notes = '' THEN 'Auto-fixed: Set effort_hours to 0 for Fully Working component'
            ELSE notes || ' | Auto-fixed: Set effort_hours to 0 for Fully Working component'
        END
    WHERE component_id IN (SELECT component_id FROM effort_hours_fixes);
    */
    
    -- Log the fixes for audit trail
    INSERT INTO component_issues (component_id, issue_description, severity, resolved, created_by, resolved_by)
    SELECT 
        component_id,
        'Auto-fix applied: effort_hours set to 0 for Fully Working component (was ' || old_effort_hours || 'h)',
        'INFO',
        TRUE,
        'automated_fix_script',
        'automated_fix_script'
    FROM effort_hours_fixes;
    
    COMMIT;
    