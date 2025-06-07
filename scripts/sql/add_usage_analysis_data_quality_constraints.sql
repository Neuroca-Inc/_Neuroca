-- Component Usage Analysis Data Quality Enhancement
-- Date: 2025-06-07
-- Purpose: Add NOT NULL constraints, validation checks, and data quality monitoring

-- =============================================================================
-- STEP 1: Add NOT NULL constraints for critical fields
-- =============================================================================

-- Create new table with proper constraints
CREATE TABLE component_usage_analysis_new (
    analysis_id INTEGER PRIMARY KEY AUTOINCREMENT,
    component_id INTEGER NOT NULL,
    expected_usage TEXT NOT NULL CHECK(length(expected_usage) > 10),
    actual_integration_status TEXT NOT NULL CHECK(length(actual_integration_status) > 5),
    missing_dependencies TEXT NOT NULL DEFAULT 'None identified',
    integration_issues TEXT NOT NULL DEFAULT 'None identified',
    usage_method TEXT NOT NULL CHECK(length(usage_method) > 5),
    working_status TEXT NOT NULL CHECK(working_status IN ('Working', 'Broken', 'Partial', 'Unknown', 'Not Tested')),
    priority_to_fix TEXT NOT NULL CHECK(priority_to_fix IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
    complexity_to_fix TEXT NOT NULL CHECK(complexity_to_fix IN ('Easy', 'Medium', 'Hard', 'Very Hard')),
    current_file_paths TEXT NOT NULL CHECK(length(current_file_paths) > 3),
    entry_points TEXT DEFAULT 'No specific entry points',
    dependencies_on TEXT NOT NULL DEFAULT 'Standard dependencies only',
    dependencies_from TEXT DEFAULT 'No dependencies identified',
    performance_impact TEXT CHECK(performance_impact IS NULL OR performance_impact IN ('Critical', 'High', 'Medium', 'Low')),
    documentation_status TEXT NOT NULL DEFAULT 'Needs documentation review',
    testing_status TEXT NOT NULL DEFAULT 'Testing status needs assessment',
    production_ready TEXT NOT NULL CHECK(production_ready IN ('Yes', 'No', 'Partial', 'Unknown')),
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT NOT NULL DEFAULT 'system',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    version INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (component_id) REFERENCES components(component_id)
);

-- Copy existing data to new table
INSERT INTO component_usage_analysis_new (
    analysis_id, component_id, expected_usage, actual_integration_status,
    missing_dependencies, integration_issues, usage_method, working_status,
    priority_to_fix, complexity_to_fix, current_file_paths, entry_points,
    dependencies_on, dependencies_from, performance_impact, documentation_status,
    testing_status, production_ready, created_at, updated_at, created_by, is_active, version
)
SELECT 
    analysis_id, 
    component_id,
    COALESCE(expected_usage, 'Usage analysis needed') as expected_usage,
    COALESCE(actual_integration_status, 'Integration status needs assessment') as actual_integration_status,
    COALESCE(missing_dependencies, 'None identified') as missing_dependencies,
    COALESCE(integration_issues, 'None identified') as integration_issues,
    COALESCE(usage_method, 'Usage method needs documentation') as usage_method,
    COALESCE(working_status, 'Unknown') as working_status,
    COALESCE(priority_to_fix, 'MEDIUM') as priority_to_fix,
    COALESCE(complexity_to_fix, 'Medium') as complexity_to_fix,
    COALESCE(current_file_paths, 'File paths need identification') as current_file_paths,
    COALESCE(entry_points, 'No specific entry points') as entry_points,
    COALESCE(dependencies_on, 'Standard dependencies only') as dependencies_on,
    COALESCE(dependencies_from, 'No dependencies identified') as dependencies_from,
    performance_impact,
    COALESCE(documentation_status, 'Needs documentation review') as documentation_status,
    COALESCE(testing_status, 'Testing status needs assessment') as testing_status,
    COALESCE(production_ready, 'No') as production_ready,
    created_at,
    updated_at,
    created_by,
    is_active,
    version
FROM component_usage_analysis;

-- Drop old table and rename new one
DROP TABLE component_usage_analysis;
ALTER TABLE component_usage_analysis_new RENAME TO component_usage_analysis;

-- =============================================================================
-- STEP 2: Create data quality validation triggers
-- =============================================================================

-- Trigger to prevent empty or too-short critical fields
CREATE TRIGGER validate_usage_analysis_quality
BEFORE INSERT ON component_usage_analysis
FOR EACH ROW
WHEN 
    length(NEW.expected_usage) < 10 OR
    length(NEW.actual_integration_status) < 5 OR
    length(NEW.usage_method) < 5 OR
    length(NEW.current_file_paths) < 3
BEGIN
    SELECT RAISE(ABORT, 'Data quality violation: Critical fields must have meaningful content');
END;

-- Trigger to update timestamp on changes
CREATE TRIGGER update_usage_analysis_timestamp
AFTER UPDATE ON component_usage_analysis
FOR EACH ROW
BEGIN
    UPDATE component_usage_analysis 
    SET updated_at = CURRENT_TIMESTAMP, version = version + 1
    WHERE analysis_id = NEW.analysis_id;
END;

-- Trigger to ensure component exists before adding usage analysis
CREATE TRIGGER validate_component_exists_usage_analysis
BEFORE INSERT ON component_usage_analysis
FOR EACH ROW
WHEN NOT EXISTS (SELECT 1 FROM components WHERE component_id = NEW.component_id)
BEGIN
    SELECT RAISE(ABORT, 'Component ID does not exist in components table');
END;

-- =============================================================================
-- STEP 3: Create data staleness detection
-- =============================================================================

-- Create table to track data freshness requirements
CREATE TABLE IF NOT EXISTS usage_analysis_freshness_rules (
    rule_id INTEGER PRIMARY KEY AUTOINCREMENT,
    component_category TEXT NOT NULL,
    max_age_days INTEGER NOT NULL DEFAULT 30,
    requires_regular_update BOOLEAN NOT NULL DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Insert default freshness rules
INSERT OR IGNORE INTO usage_analysis_freshness_rules (component_category, max_age_days, requires_regular_update)
VALUES 
    ('CLI', 14, TRUE),
    ('API', 21, TRUE),
    ('Core', 30, TRUE),
    ('Integration', 21, TRUE),
    ('Testing', 30, FALSE),
    ('Documentation', 45, FALSE);

-- =============================================================================
-- STEP 4: Create data quality monitoring views
-- =============================================================================

-- View to identify stale usage analysis records
CREATE VIEW stale_usage_analysis AS
SELECT 
    ua.component_id,
    c.component_name,
    cat.category_name,
    ua.updated_at,
    uar.max_age_days,
    ROUND(julianday('now') - julianday(ua.updated_at)) as days_since_update,
    CASE 
        WHEN ROUND(julianday('now') - julianday(ua.updated_at)) > uar.max_age_days THEN 'STALE'
        WHEN ROUND(julianday('now') - julianday(ua.updated_at)) > (uar.max_age_days * 0.8) THEN 'WARNING'
        ELSE 'FRESH'
    END as freshness_status
FROM component_usage_analysis ua
JOIN components c ON ua.component_id = c.component_id
JOIN categories cat ON c.category_id = cat.category_id
LEFT JOIN usage_analysis_freshness_rules uar ON cat.category_name = uar.component_category
WHERE ua.is_active = TRUE;

-- View to identify data quality issues
CREATE VIEW usage_analysis_quality_issues AS
SELECT 
    ua.component_id,
    c.component_name,
    CASE 
        WHEN length(ua.expected_usage) < 20 THEN 'Short expected_usage'
        WHEN length(ua.actual_integration_status) < 10 THEN 'Short integration_status'
        WHEN length(ua.usage_method) < 10 THEN 'Short usage_method'
        WHEN length(ua.current_file_paths) < 10 THEN 'Short file_paths'
        WHEN ua.working_status = 'Unknown' THEN 'Unknown working status'
        WHEN ua.production_ready = 'Unknown' THEN 'Unknown production readiness'
        ELSE 'No issues detected'
    END as quality_issue,
    ua.updated_at
FROM component_usage_analysis ua
JOIN components c ON ua.component_id = c.component_id
WHERE ua.is_active = TRUE
  AND (
    length(ua.expected_usage) < 20 OR
    length(ua.actual_integration_status) < 10 OR
    length(ua.usage_method) < 10 OR
    length(ua.current_file_paths) < 10 OR
    ua.working_status = 'Unknown' OR
    ua.production_ready = 'Unknown'
  );

-- =============================================================================
-- STEP 5: Create data quality enforcement procedures
-- =============================================================================

-- Insert validation rule into bug detection system
INSERT OR REPLACE INTO bug_alerts (
    alert_id,
    component_name,
    alert_type,
    severity,
    description,
    detection_rule,
    auto_fix_available,
    created_at
) VALUES (
    'USAGE_ANALYSIS_QUALITY',
    'Component Usage Analysis',
    'data_quality',
    'Medium',
    'Usage analysis records must have complete, meaningful data',
    'Check for NULL values, short text fields, and unknown statuses',
    FALSE,
    CURRENT_TIMESTAMP
);

-- Verification queries
SELECT 'Data Quality Constraints Added Successfully!' as status;
SELECT 'Current Quality Issues:' as info;
SELECT COUNT(*) as issue_count FROM usage_analysis_quality_issues WHERE quality_issue != 'No issues detected';
SELECT 'Stale Records:' as info;
SELECT COUNT(*) as stale_count FROM stale_usage_analysis WHERE freshness_status = 'STALE';
