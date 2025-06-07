-- =====================================================================
-- COMPREHENSIVE SYNCING TRIGGERS & DATA QUALITY ENFORCEMENT
-- =====================================================================
-- This script implements strict data quality with NOT NULL constraints
-- and comprehensive trigger-based syncing between related tables
-- =====================================================================

-- First, let's analyze current nullable fields and plan improvements
SELECT 'Data Quality Analysis - Current Nullable Fields' as section;

-- Check current NULL fields that could be made NOT NULL
SELECT 'Components nullable fields analysis:' as analysis;
SELECT 
    'component_id: ' || COUNT(CASE WHEN component_id IS NULL THEN 1 END) || ' nulls' as check_result
FROM components
UNION ALL
SELECT 'status_id: ' || COUNT(CASE WHEN status_id IS NULL THEN 1 END) || ' nulls' FROM components
UNION ALL  
SELECT 'file_path: ' || COUNT(CASE WHEN file_path IS NULL THEN 1 END) || ' nulls' FROM components
UNION ALL
SELECT 'priority: ' || COUNT(CASE WHEN priority IS NULL THEN 1 END) || ' nulls' FROM components
UNION ALL
SELECT 'effort_hours: ' || COUNT(CASE WHEN effort_hours IS NULL THEN 1 END) || ' nulls' FROM components
UNION ALL
SELECT 'notes: ' || COUNT(CASE WHEN notes IS NULL THEN 1 END) || ' nulls' FROM components;

-- Phase 1: DATA QUALITY ENFORCEMENT
-- =====================================================================

-- 1.1: Make critical fields NOT NULL where data exists
-- First, set default values for NULL fields that should have defaults

-- Set default priority for NULL priorities
UPDATE components 
SET priority = 'Medium' 
WHERE priority IS NULL;

-- Set default effort_hours for NULL effort_hours  
UPDATE components 
SET effort_hours = 8 
WHERE effort_hours IS NULL;

-- Set default notes for NULL notes
UPDATE components 
SET notes = 'Component requires documentation' 
WHERE notes IS NULL OR notes = '';

-- Set default status_id for NULL status_id (use 'Working' status)
UPDATE components 
SET status_id = (SELECT status_id FROM statuses WHERE status_name = 'Working' LIMIT 1)
WHERE status_id IS NULL;

-- 1.2: Add NOT NULL constraints via table recreation
-- Create improved components table with strict NOT NULL enforcement

CREATE TABLE components_new (
    component_id INTEGER PRIMARY KEY,
    component_name TEXT NOT NULL UNIQUE CHECK(length(component_name) >= 3),
    category_id INTEGER NOT NULL,
    status_id INTEGER NOT NULL,  -- Now NOT NULL
    file_path TEXT DEFAULT 'src/neuroca/',  -- Default path, can be NULL for virtual components
    priority TEXT NOT NULL DEFAULT 'Medium' CHECK(priority IN ('Critical', 'High', 'Medium', 'Low')),  -- Now NOT NULL
    effort_hours INTEGER NOT NULL DEFAULT 8 CHECK(effort_hours >= 0 AND effort_hours <= 200),  -- Now NOT NULL
    notes TEXT NOT NULL DEFAULT '',  -- Now NOT NULL
    duplicated BOOLEAN NOT NULL DEFAULT FALSE,
    source TEXT NOT NULL DEFAULT 'feature_inventory' CHECK(source IN ('feature_inventory', 'usage_analysis', 'manual')),
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT NOT NULL DEFAULT 'system',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    version INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (category_id) REFERENCES categories(category_id),
    FOREIGN KEY (status_id) REFERENCES statuses(status_id)
);

-- Copy data from old table to new
INSERT INTO components_new SELECT * FROM components;

-- Drop old table and rename new one
DROP TABLE components;
ALTER TABLE components_new RENAME TO components;

-- Recreate indexes for components
CREATE INDEX idx_components_category ON components(category_id);
CREATE INDEX idx_components_status ON components(status_id);
CREATE INDEX idx_components_name ON components(component_name);
CREATE INDEX idx_components_priority ON components(priority);
CREATE INDEX idx_components_active ON components(is_active);
CREATE INDEX idx_components_source ON components(source);
CREATE INDEX idx_components_created ON components(created_at);

-- 1.3: Improve component_issues with better data quality
CREATE TABLE component_issues_new (
    issue_id INTEGER PRIMARY KEY,
    component_id INTEGER NOT NULL,
    issue_description TEXT NOT NULL CHECK(length(issue_description) >= 5),
    severity TEXT NOT NULL DEFAULT 'Medium' CHECK(severity IN ('Critical', 'High', 'Medium', 'Low', 'Info')),  -- Now NOT NULL
    resolved BOOLEAN NOT NULL DEFAULT FALSE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resolved_at DATETIME,  -- Can be NULL until resolved
    created_by TEXT NOT NULL DEFAULT 'system',
    resolved_by TEXT,  -- Can be NULL until resolved
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    issue_type TEXT NOT NULL DEFAULT 'bug' CHECK(issue_type IN ('bug', 'feature', 'documentation', 'performance', 'security')),
    external_reference TEXT,  -- Can be NULL
    FOREIGN KEY (component_id) REFERENCES components(component_id) ON DELETE CASCADE
);

-- Copy existing data, setting defaults for NULL severity
INSERT INTO component_issues_new (
    issue_id, component_id, issue_description, severity, resolved, 
    created_at, updated_at, resolved_at, created_by, resolved_by, is_active, issue_type
) 
SELECT 
    issue_id, component_id, issue_description, 
    COALESCE(severity, 'Medium') as severity,
    resolved, created_at, updated_at, resolved_at, created_by, resolved_by, is_active,
    'bug' as issue_type
FROM component_issues;

DROP TABLE component_issues;
ALTER TABLE component_issues_new RENAME TO component_issues;

-- Recreate component_issues indexes
CREATE INDEX idx_comp_issues_component ON component_issues(component_id);
CREATE INDEX idx_comp_issues_severity ON component_issues(severity);
CREATE INDEX idx_comp_issues_active ON component_issues(is_active);
CREATE INDEX idx_comp_issues_resolved ON component_issues(resolved);
CREATE INDEX idx_comp_issues_created ON component_issues(created_at);
CREATE INDEX idx_comp_issues_type ON component_issues(issue_type);

-- 1.4: Improve bug_alerts to link with components properly
-- Add component_id FK to bug_alerts for proper syncing
ALTER TABLE bug_alerts ADD COLUMN component_id INTEGER;

-- Update component_id based on component_name where possible
UPDATE bug_alerts 
SET component_id = (
    SELECT component_id 
    FROM components 
    WHERE component_name = bug_alerts.component_name 
    LIMIT 1
) 
WHERE component_name IS NOT NULL;

-- Create improved bug_alerts table
CREATE TABLE bug_alerts_new (
    alert_id INTEGER PRIMARY KEY AUTOINCREMENT,
    alert_type TEXT NOT NULL,
    severity TEXT NOT NULL CHECK (severity IN ('CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO')),
    component_id INTEGER,  -- Can be NULL for system-wide alerts
    component_name TEXT NOT NULL DEFAULT 'system',  -- Default for system alerts
    description TEXT NOT NULL,
    detected_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    auto_generated BOOLEAN NOT NULL DEFAULT TRUE,
    raw_data TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resolved_by TEXT,  -- Can be NULL until resolved
    FOREIGN KEY (component_id) REFERENCES components(component_id) ON DELETE SET NULL
);

-- Copy data to new table
INSERT INTO bug_alerts_new SELECT * FROM bug_alerts;
DROP TABLE bug_alerts;
ALTER TABLE bug_alerts_new RENAME TO bug_alerts;

-- Recreate bug_alerts indexes  
CREATE INDEX idx_bug_alerts_type ON bug_alerts(alert_type);
CREATE INDEX idx_bug_alerts_severity ON bug_alerts(severity);
CREATE INDEX idx_bug_alerts_component ON bug_alerts(component_id);
CREATE INDEX idx_bug_alerts_active ON bug_alerts(is_active);
CREATE INDEX idx_bug_alerts_detected ON bug_alerts(detected_at);

-- Phase 2: COMPREHENSIVE SYNCING TRIGGERS
-- =====================================================================

-- 2.1: Bug Detection → Component Issues Syncing
-- When bug_alerts are created/updated, sync to component_issues

CREATE TRIGGER sync_bug_to_component_issue_insert
AFTER INSERT ON bug_alerts
WHEN NEW.component_id IS NOT NULL AND NEW.is_active = TRUE
BEGIN
    -- Create corresponding component_issue for active bug alerts
    INSERT OR IGNORE INTO component_issues (
        component_id, issue_description, severity, issue_type, 
        created_by, external_reference
    ) VALUES (
        NEW.component_id,
        'Bug Alert: ' || NEW.description,
        CASE NEW.severity
            WHEN 'CRITICAL' THEN 'Critical'
            WHEN 'HIGH' THEN 'High' 
            WHEN 'MEDIUM' THEN 'Medium'
            WHEN 'LOW' THEN 'Low'
            WHEN 'INFO' THEN 'Info'
        END,
        'bug',
        'bug_detection_system',
        'bug_alert_' || NEW.alert_id
    );
END;

-- 2.2: Bug Resolution → Component Issues Resolution Syncing
CREATE TRIGGER sync_bug_resolution_to_component_issue
AFTER UPDATE ON bug_alerts
WHEN NEW.resolved_at IS NOT NULL AND OLD.resolved_at IS NULL
BEGIN
    -- Mark corresponding component_issue as resolved
    UPDATE component_issues 
    SET 
        resolved = TRUE,
        resolved_at = NEW.resolved_at,
        resolved_by = COALESCE(NEW.resolved_by, 'bug_detection_system'),
        updated_at = CURRENT_TIMESTAMP
    WHERE external_reference = 'bug_alert_' || NEW.alert_id;
END;

-- 2.3: Component Status Changes → Usage Analysis Syncing  
CREATE TRIGGER sync_component_status_to_usage_analysis
AFTER UPDATE ON components
WHEN NEW.status_id != OLD.status_id
BEGIN
    -- Update usage analysis when component status changes
    UPDATE component_usage_analysis
    SET 
        usage_analysis_status = (SELECT status_name FROM statuses WHERE status_id = NEW.status_id),
        updated_at = CURRENT_TIMESTAMP
    WHERE component_id = NEW.component_id;
    
    -- If component becomes 'Broken', create an issue
    INSERT INTO component_issues (
        component_id, issue_description, severity, issue_type, created_by
    )
    SELECT 
        NEW.component_id,
        'Component status changed to: ' || s.status_name,
        'High',
        'performance',
        'status_monitor'
    FROM statuses s 
    WHERE s.status_id = NEW.status_id 
    AND s.status_name IN ('Broken', 'Failed', 'Error');
END;

-- 2.4: Component Priority Changes → Usage Analysis Priority Syncing
CREATE TRIGGER sync_component_priority_to_usage_analysis
AFTER UPDATE ON components  
WHEN NEW.priority != OLD.priority
BEGIN
    UPDATE component_usage_analysis
    SET 
        priority = NEW.priority,
        updated_at = CURRENT_TIMESTAMP
    WHERE component_id = NEW.component_id;
END;

-- 2.5: Component Issues → Component Status Syncing
-- When critical issues are created, update component status
CREATE TRIGGER sync_critical_issue_to_component_status
AFTER INSERT ON component_issues
WHEN NEW.severity = 'Critical' AND NEW.is_active = TRUE
BEGIN
    -- Update component status to indicate critical issue
    UPDATE components
    SET 
        updated_at = CURRENT_TIMESTAMP,
        -- Add note about critical issue
        notes = CASE 
            WHEN notes LIKE '%CRITICAL ISSUE:%' THEN notes
            ELSE notes || CHAR(10) || 'CRITICAL ISSUE: ' || NEW.issue_description
        END
    WHERE component_id = NEW.component_id;
    
    -- Create high-priority bug alert if not auto-generated
    INSERT INTO bug_alerts (
        alert_type, severity, component_id, component_name, description, created_by
    ) VALUES (
        'CRITICAL_ISSUE',
        'CRITICAL', 
        NEW.component_id,
        (SELECT component_name FROM components WHERE component_id = NEW.component_id),
        'Critical component issue: ' || NEW.issue_description,
        'issue_escalation_system'
    );
END;

-- 2.6: File Activity → Component Status Syncing
-- When files are heavily modified, update component usage tracking
CREATE TRIGGER sync_file_activity_to_component_usage
AFTER INSERT ON file_activity_log
WHEN NEW.component_id IS NOT NULL
BEGIN
    -- Update usage analysis based on file activity
    UPDATE component_usage_analysis
    SET 
        updated_at = CURRENT_TIMESTAMP,
        -- Increment activity counters (simplified logic)
        production_ready_percentage = CASE 
            WHEN NEW.change_type = 'modified' AND NEW.is_test_file = FALSE 
            THEN MIN(100, production_ready_percentage + 1)
            ELSE production_ready_percentage
        END
    WHERE component_id = NEW.component_id;
END;

-- 2.7: Component Deletion → Cascade Cleanup Trigger
CREATE TRIGGER cleanup_component_deletion
AFTER UPDATE ON components
WHEN NEW.is_active = FALSE AND OLD.is_active = TRUE
BEGIN
    -- Mark related records as inactive instead of deleting
    UPDATE component_issues SET is_active = FALSE WHERE component_id = NEW.component_id;
    UPDATE component_usage_analysis SET is_active = FALSE WHERE component_id = NEW.component_id;
    UPDATE bug_alerts SET is_active = FALSE WHERE component_id = NEW.component_id;
    
    -- Log the deactivation
    INSERT INTO audit_log (table_name, record_id, operation, changed_by)
    VALUES ('components', NEW.component_id, 'DEACTIVATED', 'system');
END;

-- Phase 3: DATA CONSISTENCY VALIDATION TRIGGERS
-- =====================================================================

-- 3.1: Prevent orphaned records
CREATE TRIGGER prevent_orphaned_component_issues
BEFORE INSERT ON component_issues
BEGIN
    SELECT CASE 
        WHEN (SELECT COUNT(*) FROM components WHERE component_id = NEW.component_id AND is_active = TRUE) = 0
        THEN RAISE(ABORT, 'Cannot create issue for inactive or non-existent component')
    END;
END;

-- 3.2: Ensure bug alert component consistency
CREATE TRIGGER ensure_bug_alert_component_consistency
BEFORE INSERT ON bug_alerts
WHEN NEW.component_id IS NOT NULL
BEGIN
    SELECT CASE
        WHEN (SELECT COUNT(*) FROM components WHERE component_id = NEW.component_id AND is_active = TRUE) = 0
        THEN RAISE(ABORT, 'Cannot create bug alert for inactive or non-existent component')
    END;
END;

-- 3.3: Ensure usage analysis component consistency  
CREATE TRIGGER ensure_usage_analysis_component_consistency
BEFORE INSERT ON component_usage_analysis
BEGIN
    SELECT CASE
        WHEN (SELECT COUNT(*) FROM components WHERE component_id = NEW.component_id AND is_active = TRUE) = 0
        THEN RAISE(ABORT, 'Cannot create usage analysis for inactive or non-existent component')
    END;
END;

-- Phase 4: PERFORMANCE & MAINTENANCE TRIGGERS
-- =====================================================================

-- 4.1: Auto-cleanup resolved issues after 30 days
CREATE TRIGGER auto_cleanup_old_resolved_issues
AFTER UPDATE ON component_issues
WHEN NEW.resolved = TRUE AND OLD.resolved = FALSE
BEGIN
    -- Schedule cleanup of very old resolved issues (simplified)
    UPDATE component_issues 
    SET is_active = FALSE 
    WHERE resolved = TRUE 
    AND resolved_at < datetime('now', '-30 days')
    AND severity IN ('Low', 'Info');
END;

-- 4.2: Auto-resolve duplicate issues
CREATE TRIGGER prevent_duplicate_issues
BEFORE INSERT ON component_issues
BEGIN
    SELECT CASE
        WHEN EXISTS (
            SELECT 1 FROM component_issues 
            WHERE component_id = NEW.component_id 
            AND issue_description = NEW.issue_description
            AND resolved = FALSE
            AND is_active = TRUE
        )
        THEN RAISE(ABORT, 'Duplicate active issue exists for this component')
    END;
END;

-- Phase 5: VALIDATION & SUMMARY
-- =====================================================================

-- Validate all syncing triggers are created
SELECT 'Syncing System Validation' as validation_type
UNION ALL
SELECT 'Total Triggers: ' || COUNT(*) FROM sqlite_master WHERE type='trigger'
UNION ALL
SELECT 'Syncing Triggers: ' || COUNT(*) FROM sqlite_master WHERE type='trigger' AND name LIKE '%sync%'
UNION ALL
SELECT 'Data Quality Triggers: ' || COUNT(*) FROM sqlite_master WHERE type='trigger' AND (name LIKE '%prevent%' OR name LIKE '%ensure%')
UNION ALL
SELECT 'Maintenance Triggers: ' || COUNT(*) FROM sqlite_master WHERE type='trigger' AND (name LIKE '%cleanup%' OR name LIKE '%auto%');

-- Final data quality check
SELECT 'Data Quality Final Check' as check_type
UNION ALL
SELECT 'Components with NULL status_id: ' || COUNT(*) FROM components WHERE status_id IS NULL
UNION ALL  
SELECT 'Components with NULL priority: ' || COUNT(*) FROM components WHERE priority IS NULL
UNION ALL
SELECT 'Component_issues with NULL severity: ' || COUNT(*) FROM component_issues WHERE severity IS NULL
UNION ALL
SELECT 'Bug_alerts with NULL description: ' || COUNT(*) FROM bug_alerts WHERE description IS NULL OR description = '';

SELECT 'Comprehensive Syncing & Data Quality System COMPLETE' as completion_status, 
       datetime('now') as completed_at;
