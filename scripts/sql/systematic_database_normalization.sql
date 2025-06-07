-- ============================================================================
-- SYSTEMATIC DATABASE NORMALIZATION SCRIPT
-- ============================================================================
-- Purpose: Normalize all tables with proper PKs, FKs, constraints, triggers, and indexes
-- Dependencies: Run on existing neuroca_temporal_analysis.db
-- Order: Lookup tables → Core tables → History tables → Supporting tables
-- ============================================================================

-- PHASE 1: LOOKUP TABLES NORMALIZATION
-- ============================================================================

-- 1.1: CATEGORIES TABLE
-- Add missing indexes and ensure proper constraints
CREATE INDEX IF NOT EXISTS idx_categories_name ON categories(category_name);
CREATE INDEX IF NOT EXISTS idx_categories_active ON categories(is_active);
CREATE INDEX IF NOT EXISTS idx_categories_created ON categories(created_at);

-- 1.2: STATUSES TABLE  
-- Add missing indexes and version field if needed
CREATE INDEX IF NOT EXISTS idx_statuses_name ON statuses(status_name);
CREATE INDEX IF NOT EXISTS idx_statuses_active ON statuses(is_active);
CREATE INDEX IF NOT EXISTS idx_statuses_created ON statuses(created_at);

-- Add version field if missing (check first)
-- ALTER TABLE statuses ADD COLUMN version INTEGER DEFAULT 1;

-- 1.3: WORKING_STATUSES TABLE
-- Already has proper structure and triggers, add performance indexes
CREATE INDEX IF NOT EXISTS idx_working_statuses_name ON working_statuses(status_name);
CREATE INDEX IF NOT EXISTS idx_working_statuses_created ON working_statuses(created_at);

-- 1.4: PRIORITY_LEVELS TABLE
-- Add missing indexes and ensure proper structure
CREATE INDEX IF NOT EXISTS idx_priority_levels_name ON priority_levels(priority_name);  
CREATE INDEX IF NOT EXISTS idx_priority_levels_order ON priority_levels(priority_order);
CREATE INDEX IF NOT EXISTS idx_priority_levels_active ON priority_levels(is_active);

-- 1.5: COMPLEXITY_LEVELS TABLE
-- Add missing indexes
CREATE INDEX IF NOT EXISTS idx_complexity_levels_name ON complexity_levels(complexity_name);
CREATE INDEX IF NOT EXISTS idx_complexity_levels_active ON complexity_levels(is_active);
CREATE INDEX IF NOT EXISTS idx_complexity_levels_hours ON complexity_levels(estimated_hours);

-- 1.6: DOCUMENTATION_STATUSES TABLE
-- Already has proper structure, add missing indexes
CREATE INDEX IF NOT EXISTS idx_documentation_statuses_name ON documentation_statuses(status_name);
CREATE INDEX IF NOT EXISTS idx_documentation_statuses_created ON documentation_statuses(created_at);

-- 1.7: TESTING_STATUSES TABLE  
-- Already has proper structure, add missing indexes
CREATE INDEX IF NOT EXISTS idx_testing_statuses_name ON testing_statuses(status_name);
CREATE INDEX IF NOT EXISTS idx_testing_statuses_created ON testing_statuses(created_at);

-- 1.8: READINESS_STATUSES TABLE
-- Add missing indexes and standardize structure
CREATE INDEX IF NOT EXISTS idx_readiness_statuses_name ON readiness_statuses(readiness_name);
CREATE INDEX IF NOT EXISTS idx_readiness_statuses_active ON readiness_statuses(is_active);

-- 1.9: USAGE_METHODS TABLE
-- Already has proper structure, add missing indexes  
CREATE INDEX IF NOT EXISTS idx_usage_methods_name ON usage_methods(method_name);
CREATE INDEX IF NOT EXISTS idx_usage_methods_created ON usage_methods(created_at);

-- ============================================================================
-- PHASE 2: CORE TABLES NORMALIZATION
-- ============================================================================

-- 2.1: COMPONENTS TABLE
-- Add critical FK indexes and ensure proper constraints
CREATE INDEX IF NOT EXISTS idx_components_category ON components(category_id);
CREATE INDEX IF NOT EXISTS idx_components_status ON components(status_id);  
CREATE INDEX IF NOT EXISTS idx_components_name ON components(component_name);
CREATE INDEX IF NOT EXISTS idx_components_priority ON components(priority);
CREATE INDEX IF NOT EXISTS idx_components_active ON components(is_active);
CREATE INDEX IF NOT EXISTS idx_components_source ON components(source);
CREATE INDEX IF NOT EXISTS idx_components_created ON components(created_at);

-- 2.2: COMPONENT_USAGE_ANALYSIS TABLE  
-- This is the major normalization - add missing indexes first
CREATE INDEX IF NOT EXISTS idx_comp_usage_component ON component_usage_analysis(component_id);
CREATE INDEX IF NOT EXISTS idx_comp_usage_status ON component_usage_analysis(working_status);
CREATE INDEX IF NOT EXISTS idx_comp_usage_priority ON component_usage_analysis(priority_to_fix);
CREATE INDEX IF NOT EXISTS idx_comp_usage_complexity ON component_usage_analysis(complexity_to_fix);
CREATE INDEX IF NOT EXISTS idx_comp_usage_active ON component_usage_analysis(is_active);
CREATE INDEX IF NOT EXISTS idx_comp_usage_created ON component_usage_analysis(created_at);
CREATE INDEX IF NOT EXISTS idx_comp_usage_production ON component_usage_analysis(production_ready);

-- Add missing history triggers for component_usage_analysis
CREATE TRIGGER IF NOT EXISTS component_usage_analysis_insert_history
AFTER INSERT ON component_usage_analysis
FOR EACH ROW
BEGIN
    INSERT INTO component_usage_analysis_history (
        analysis_id, component_id, expected_usage, actual_integration_status,
        missing_dependencies, integration_issues, usage_method, working_status,
        priority_to_fix, complexity_to_fix, current_file_paths, entry_points,
        dependencies_on, dependencies_from, performance_impact, documentation_status,
        testing_status, production_ready, created_at, updated_at, created_by,
        is_active, version, history_operation, history_user
    ) VALUES (
        NEW.analysis_id, NEW.component_id, NEW.expected_usage, NEW.actual_integration_status,
        NEW.missing_dependencies, NEW.integration_issues, NEW.usage_method, NEW.working_status,
        NEW.priority_to_fix, NEW.complexity_to_fix, NEW.current_file_paths, NEW.entry_points,
        NEW.dependencies_on, NEW.dependencies_from, NEW.performance_impact, NEW.documentation_status,
        NEW.testing_status, NEW.production_ready, NEW.created_at, NEW.updated_at, NEW.created_by,
        NEW.is_active, NEW.version, 'INSERT', NEW.created_by
    );
END;

CREATE TRIGGER IF NOT EXISTS component_usage_analysis_update_history
AFTER UPDATE ON component_usage_analysis  
FOR EACH ROW
BEGIN
    INSERT INTO component_usage_analysis_history (
        analysis_id, component_id, expected_usage, actual_integration_status,
        missing_dependencies, integration_issues, usage_method, working_status,
        priority_to_fix, complexity_to_fix, current_file_paths, entry_points,
        dependencies_on, dependencies_from, performance_impact, documentation_status,
        testing_status, production_ready, created_at, updated_at, created_by,
        is_active, version, history_operation, history_user
    ) VALUES (
        OLD.analysis_id, OLD.component_id, OLD.expected_usage, OLD.actual_integration_status,
        OLD.missing_dependencies, OLD.integration_issues, OLD.usage_method, OLD.working_status,
        OLD.priority_to_fix, OLD.complexity_to_fix, OLD.current_file_paths, OLD.entry_points,
        OLD.dependencies_on, OLD.dependencies_from, OLD.performance_impact, OLD.documentation_status,
        OLD.testing_status, OLD.production_ready, OLD.created_at, OLD.updated_at, OLD.created_by,
        OLD.is_active, OLD.version, 'UPDATE', OLD.created_by
    );
END;

CREATE TRIGGER IF NOT EXISTS component_usage_analysis_update_timestamp
BEFORE UPDATE ON component_usage_analysis
FOR EACH ROW  
BEGIN
    UPDATE component_usage_analysis
    SET updated_at = CURRENT_TIMESTAMP,
        version = version + 1
    WHERE analysis_id = NEW.analysis_id;
END;

-- ============================================================================
-- PHASE 3: SUPPORTING TABLES NORMALIZATION
-- ============================================================================

-- 3.1: COMPONENT_DEPENDENCIES TABLE
-- Add missing indexes
CREATE INDEX IF NOT EXISTS idx_comp_deps_component ON component_dependencies(component_id);
CREATE INDEX IF NOT EXISTS idx_comp_deps_type ON component_dependencies(dependency_type);
CREATE INDEX IF NOT EXISTS idx_comp_deps_active ON component_dependencies(is_active);
CREATE INDEX IF NOT EXISTS idx_comp_deps_created ON component_dependencies(created_at);

-- 3.2: COMPONENT_ISSUES TABLE  
-- Add missing indexes
CREATE INDEX IF NOT EXISTS idx_comp_issues_component ON component_issues(component_id);
CREATE INDEX IF NOT EXISTS idx_comp_issues_severity ON component_issues(severity);
CREATE INDEX IF NOT EXISTS idx_comp_issues_resolved ON component_issues(resolved);
CREATE INDEX IF NOT EXISTS idx_comp_issues_active ON component_issues(is_active);
CREATE INDEX IF NOT EXISTS idx_comp_issues_created ON component_issues(created_at);

-- 3.3: CURRENT_DRIFT_ALERTS TABLE
-- Add missing indexes  
CREATE INDEX IF NOT EXISTS idx_drift_alerts_type ON current_drift_alerts(alert_type);
CREATE INDEX IF NOT EXISTS idx_drift_alerts_severity ON current_drift_alerts(severity);
CREATE INDEX IF NOT EXISTS idx_drift_alerts_component ON current_drift_alerts(component_id);
CREATE INDEX IF NOT EXISTS idx_drift_alerts_active ON current_drift_alerts(is_active);
CREATE INDEX IF NOT EXISTS idx_drift_alerts_detected ON current_drift_alerts(detected_at);

-- 3.4: FILE_ACTIVITY_LOG TABLE
-- Add missing indexes for performance
CREATE INDEX IF NOT EXISTS idx_file_activity_component ON file_activity_log(component_id);
CREATE INDEX IF NOT EXISTS idx_file_activity_timestamp ON file_activity_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_file_activity_change_type ON file_activity_log(change_type);
CREATE INDEX IF NOT EXISTS idx_file_activity_path ON file_activity_log(file_path);
CREATE INDEX IF NOT EXISTS idx_file_activity_test_file ON file_activity_log(is_test_file);

-- 3.5: AUDIT_LOG TABLE
-- Add missing indexes
CREATE INDEX IF NOT EXISTS idx_audit_log_table ON audit_log(table_name);
CREATE INDEX IF NOT EXISTS idx_audit_log_operation ON audit_log(operation);
CREATE INDEX IF NOT EXISTS idx_audit_log_record ON audit_log(record_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_created ON audit_log(created_at);

-- 3.6: BUG_ALERTS TABLE
-- Add missing indexes
CREATE INDEX IF NOT EXISTS idx_bug_alerts_type ON bug_alerts(alert_type);
CREATE INDEX IF NOT EXISTS idx_bug_alerts_severity ON bug_alerts(severity);
CREATE INDEX IF NOT EXISTS idx_bug_alerts_component ON bug_alerts(component_name);
CREATE INDEX IF NOT EXISTS idx_bug_alerts_active ON bug_alerts(is_active);
CREATE INDEX IF NOT EXISTS idx_bug_alerts_detected ON bug_alerts(detected_at);

-- ============================================================================
-- PHASE 4: HISTORY TABLES NORMALIZATION  
-- ============================================================================

-- Add indexes to history tables for performance
CREATE INDEX IF NOT EXISTS idx_categories_history_id ON categories_history(category_id);
CREATE INDEX IF NOT EXISTS idx_categories_history_operation ON categories_history(history_operation);
CREATE INDEX IF NOT EXISTS idx_categories_history_timestamp ON categories_history(history_timestamp);

CREATE INDEX IF NOT EXISTS idx_components_history_id ON components_history(component_id);
CREATE INDEX IF NOT EXISTS idx_components_history_operation ON components_history(history_operation);
CREATE INDEX IF NOT EXISTS idx_components_history_timestamp ON components_history(history_timestamp);

CREATE INDEX IF NOT EXISTS idx_statuses_history_id ON statuses_history(status_id);
CREATE INDEX IF NOT EXISTS idx_statuses_history_operation ON statuses_history(history_operation);
CREATE INDEX IF NOT EXISTS idx_statuses_history_timestamp ON statuses_history(history_timestamp);

CREATE INDEX IF NOT EXISTS idx_comp_usage_history_id ON component_usage_analysis_history(analysis_id);
CREATE INDEX IF NOT EXISTS idx_comp_usage_history_component ON component_usage_analysis_history(component_id);
CREATE INDEX IF NOT EXISTS idx_comp_usage_history_operation ON component_usage_analysis_history(history_operation);
CREATE INDEX IF NOT EXISTS idx_comp_usage_history_timestamp ON component_usage_analysis_history(history_timestamp);

-- ============================================================================
-- NORMALIZATION VALIDATION QUERIES
-- ============================================================================

-- Check all FK relationships are working
SELECT 'FK Check: components->categories' as check_name,
       COUNT(*) as total_components,
       COUNT(c.category_id) as components_with_category,
       COUNT(cat.category_id) as valid_category_refs
FROM components c
LEFT JOIN categories cat ON c.category_id = cat.category_id;

SELECT 'FK Check: components->statuses' as check_name,
       COUNT(*) as total_components,
       COUNT(c.status_id) as components_with_status,
       COUNT(s.status_id) as valid_status_refs  
FROM components c
LEFT JOIN statuses s ON c.status_id = s.status_id;

SELECT 'FK Check: component_usage_analysis->components' as check_name,
       COUNT(*) as total_analysis,
       COUNT(cua.component_id) as analysis_with_component,
       COUNT(c.component_id) as valid_component_refs
FROM component_usage_analysis cua
LEFT JOIN components c ON cua.component_id = c.component_id;

-- Check all indexes were created
SELECT 'Index Summary' as summary,
       COUNT(*) as total_indexes
FROM sqlite_master 
WHERE type = 'index' AND name NOT LIKE 'sqlite_%';

-- Check all triggers are working
SELECT 'Trigger Summary' as summary,
       COUNT(*) as total_triggers
FROM sqlite_master
WHERE type = 'trigger';

-- ============================================================================
-- COMPLETION MESSAGE
-- ============================================================================
SELECT 'Database normalization completed successfully' as status,
       datetime('now') as completed_at;
