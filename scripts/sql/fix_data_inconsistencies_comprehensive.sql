-- =====================================================================
-- COMPREHENSIVE DATA INCONSISTENCY FIXES
-- =====================================================================
-- This script addresses the logical inconsistencies identified in the database
-- ensuring data makes logical sense and follows business rules
-- =====================================================================

SELECT 'COMPREHENSIVE DATA INCONSISTENCY FIXES' as section
UNION ALL
SELECT 'Starting at: ' || datetime('now')
UNION ALL  
SELECT '=============================================';

-- Phase 1: Fix Broken Components with 0 Effort Hours
-- =====================================================================
-- ISSUE: Broken components should require effort to fix

UPDATE components 
SET effort_hours = CASE component_name
    WHEN 'API Routes' THEN 12  -- Critical component, substantial effort needed
    WHEN 'CLI Interface' THEN 8   -- Medium priority, moderate effort
    ELSE 6  -- Default for other broken components
END,
updated_at = CURRENT_TIMESTAMP
WHERE component_id IN (
    SELECT c.component_id 
    FROM components c
    JOIN statuses s ON c.status_id = s.status_id
    WHERE s.status_name = 'Broken' AND c.effort_hours = 0
);

-- Phase 2: Fix Working Components with High Priority
-- =====================================================================
-- ISSUE: Fully Working components shouldn't have High priority unless maintenance

UPDATE components 
SET priority = CASE 
    WHEN component_name = 'API Authentication' THEN 'Medium'  -- Important but working
    WHEN component_name = 'Main Application' THEN 'Medium'   -- Core but stable
    ELSE 'Low'  -- Default for other fully working components
END,
updated_at = CURRENT_TIMESTAMP
WHERE component_id IN (
    SELECT c.component_id 
    FROM components c
    JOIN statuses s ON c.status_id = s.status_id
    WHERE s.status_name IN ('Fully Working', 'Working') AND c.priority = 'High'
);

-- Phase 3: Fix Missing Components Priority Logic  
-- =====================================================================
-- ISSUE: Missing critical components should have higher priority

UPDATE components 
SET priority = CASE 
    WHEN component_name IN ('Logging System', 'Production Config', 'Security Audit') THEN 'High'
    WHEN component_name LIKE '%API%' OR component_name LIKE '%CLI%' THEN 'High'
    WHEN component_name LIKE '%System%' OR component_name LIKE '%Service%' THEN 'Medium'
    ELSE 'Medium'  -- Default increase from Low
END,
updated_at = CURRENT_TIMESTAMP
WHERE component_id IN (
    SELECT c.component_id 
    FROM components c
    JOIN statuses s ON c.status_id = s.status_id
    WHERE s.status_name = 'Missing' AND c.priority = 'Low'
);

-- Phase 4: Fix Effort Hours for Critical Missing Components
-- =====================================================================
-- ISSUE: Missing components should have realistic effort estimates

UPDATE components 
SET effort_hours = CASE component_name
    WHEN 'Logging System' THEN 16       -- Complex system implementation
    WHEN 'Production Config' THEN 12    -- Configuration setup and testing
    WHEN 'Security Audit' THEN 20       -- Comprehensive security review
    WHEN 'Memory Service Layer' THEN 14 -- Service layer implementation
    WHEN 'User Management System' THEN 18 -- User system is complex
    ELSE GREATEST(effort_hours, 8)      -- Minimum 8 hours for missing components
END,
updated_at = CURRENT_TIMESTAMP
WHERE component_id IN (
    SELECT c.component_id 
    FROM components c
    JOIN statuses s ON c.status_id = s.status_id
    WHERE s.status_name = 'Missing'
);

-- Phase 5: Fix Working Memory Item Validation Error Status
-- =====================================================================
-- ISSUE: This is a critical blocker but has inconsistent status

UPDATE components 
SET status_id = (SELECT status_id FROM statuses WHERE status_name = 'Broken'),
    priority = 'Critical',
    effort_hours = 8,
    notes = 'CRITICAL BLOCKER: WorkingMemoryItem validation error prevents functional working memory integration. Pydantic V1->V2 migration issue.',
    updated_at = CURRENT_TIMESTAMP
WHERE component_name = 'Working Memory Item Validation Error';

-- Phase 6: Adjust Production Ready Components with Realistic Effort
-- =====================================================================
-- ISSUE: Production ready components still need maintenance effort

UPDATE components 
SET effort_hours = CASE 
    WHEN effort_hours = 0 AND component_name LIKE '%System%' THEN 4  -- Maintenance effort
    WHEN effort_hours = 0 AND component_name LIKE '%API%' THEN 6     -- API maintenance
    WHEN effort_hours = 0 THEN 2  -- Minimal maintenance for others
    ELSE effort_hours
END,
updated_at = CURRENT_TIMESTAMP
WHERE component_id IN (
    SELECT c.component_id 
    FROM components c
    JOIN statuses s ON c.status_id = s.status_id
    WHERE s.status_name IN ('Fully Working', 'Working') AND c.effort_hours = 0
);

-- Phase 7: Update Usage Analysis to Match Component Changes
-- =====================================================================
-- Sync the changes to usage analysis table

UPDATE component_usage_analysis 
SET priority = (SELECT priority FROM components WHERE components.component_id = component_usage_analysis.component_id),
    updated_at = CURRENT_TIMESTAMP
WHERE component_id IN (
    SELECT component_id FROM components 
    WHERE updated_at > datetime('now', '-5 minutes')
);

-- Phase 8: Create Issues for Newly Identified Critical Problems
-- =====================================================================

-- Create issue for broken components that need immediate attention
INSERT INTO component_issues (component_id, issue_description, severity, issue_type, created_by)
SELECT 
    c.component_id,
    'Component requires immediate attention - Status: ' || s.status_name || ', Priority: ' || c.priority,
    'Critical',
    'bug',
    'data_consistency_fix'
FROM components c
JOIN statuses s ON c.status_id = s.status_id
WHERE s.status_name = 'Broken' 
AND NOT EXISTS (
    SELECT 1 FROM component_issues ci 
    WHERE ci.component_id = c.component_id 
    AND ci.severity = 'Critical' 
    AND ci.resolved = FALSE
);

-- Create issues for missing critical components
INSERT INTO component_issues (component_id, issue_description, severity, issue_type, created_by)
SELECT 
    c.component_id,
    'Critical missing component: ' || c.component_name || ' - Required for production readiness',
    'High',
    'feature',
    'data_consistency_fix'
FROM components c
JOIN statuses s ON c.status_id = s.status_id
WHERE s.status_name = 'Missing' 
AND c.priority IN ('Critical', 'High')
AND NOT EXISTS (
    SELECT 1 FROM component_issues ci 
    WHERE ci.component_id = c.component_id 
    AND ci.severity IN ('Critical', 'High') 
    AND ci.resolved = FALSE
);

-- Phase 9: Validation & Summary
-- =====================================================================

SELECT 'VALIDATION RESULTS:' as validation_section
UNION ALL
SELECT 'Broken components with 0 effort: ' || COUNT(*)
FROM components c
JOIN statuses s ON c.status_id = s.status_id
WHERE s.status_name = 'Broken' AND c.effort_hours = 0
UNION ALL
SELECT 'Working components with High priority: ' || COUNT(*)
FROM components c
JOIN statuses s ON c.status_id = s.status_id  
WHERE s.status_name IN ('Fully Working', 'Working') AND c.priority = 'High'
UNION ALL
SELECT 'Missing components with Low priority: ' || COUNT(*)
FROM components c
JOIN statuses s ON c.status_id = s.status_id
WHERE s.status_name = 'Missing' AND c.priority = 'Low'
UNION ALL
SELECT 'Components updated in this session: ' || COUNT(*)
FROM components 
WHERE updated_at > datetime('now', '-5 minutes');

SELECT 'COMPREHENSIVE DATA INCONSISTENCY FIXES COMPLETE' as completion_status, 
       datetime('now') as completed_at;
