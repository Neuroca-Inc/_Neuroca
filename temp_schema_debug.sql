CREATE TABLE categories (
        category_id INTEGER PRIMARY KEY,
        category_name TEXT UNIQUE NOT NULL CHECK(length(category_name) >= 2),
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        created_by TEXT DEFAULT 'system',
        is_active BOOLEAN DEFAULT TRUE
    );
CREATE TABLE categories_history (
        history_id INTEGER PRIMARY KEY,
        category_id INTEGER NOT NULL,
        category_name TEXT NOT NULL,
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL,
        created_by TEXT NOT NULL,
        is_active BOOLEAN NOT NULL,
        history_operation TEXT NOT NULL CHECK(history_operation IN ('INSERT', 'UPDATE', 'DELETE')),
        history_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        history_user TEXT DEFAULT 'system'
    );
CREATE TABLE statuses (
        status_id INTEGER PRIMARY KEY,
        status_name TEXT UNIQUE NOT NULL CHECK(length(status_name) >= 3),
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        created_by TEXT DEFAULT 'system',
        is_active BOOLEAN DEFAULT TRUE
    );
CREATE TABLE statuses_history (
        history_id INTEGER PRIMARY KEY,
        status_id INTEGER NOT NULL,
        status_name TEXT NOT NULL,
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL,
        created_by TEXT NOT NULL,
        is_active BOOLEAN NOT NULL,
        history_operation TEXT NOT NULL CHECK(history_operation IN ('INSERT', 'UPDATE', 'DELETE')),
        history_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        history_user TEXT DEFAULT 'system'
    );
CREATE TABLE components_history (
        history_id INTEGER PRIMARY KEY,
        component_id INTEGER NOT NULL,
        component_name TEXT NOT NULL,
        category_id INTEGER NOT NULL,
        status_id INTEGER,
        file_path TEXT,
        priority TEXT,
        effort_hours INTEGER,
        notes TEXT,
        duplicated BOOLEAN NOT NULL,
        source TEXT NOT NULL,
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL,
        created_by TEXT NOT NULL,
        is_active BOOLEAN NOT NULL,
        version INTEGER NOT NULL,
        history_operation TEXT NOT NULL CHECK(history_operation IN ('INSERT', 'UPDATE', 'DELETE')),
        history_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        history_user TEXT DEFAULT 'system'
    );
CREATE TABLE component_dependencies (
        dependency_id INTEGER PRIMARY KEY,
        component_id INTEGER NOT NULL,
        depends_on TEXT NOT NULL CHECK(length(depends_on) >= 1),
        dependency_type TEXT DEFAULT 'requires' CHECK(dependency_type IN ('requires', 'optional', 'suggests', 'conflicts')),
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        created_by TEXT DEFAULT 'system',
        is_active BOOLEAN DEFAULT TRUE,
        FOREIGN KEY (component_id) REFERENCES components(component_id) ON DELETE CASCADE
    );
CREATE TABLE component_dependencies_history (
        history_id INTEGER PRIMARY KEY,
        dependency_id INTEGER NOT NULL,
        component_id INTEGER NOT NULL,
        depends_on TEXT NOT NULL,
        dependency_type TEXT NOT NULL,
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL,
        created_by TEXT NOT NULL,
        is_active BOOLEAN NOT NULL,
        history_operation TEXT NOT NULL CHECK(history_operation IN ('INSERT', 'UPDATE', 'DELETE')),
        history_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        history_user TEXT DEFAULT 'system'
    );
CREATE TABLE component_issues_history (
        history_id INTEGER PRIMARY KEY,
        issue_id INTEGER NOT NULL,
        component_id INTEGER NOT NULL,
        issue_description TEXT NOT NULL,
        severity TEXT,
        resolved BOOLEAN NOT NULL,
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL,
        resolved_at DATETIME,
        created_by TEXT NOT NULL,
        resolved_by TEXT,
        is_active BOOLEAN NOT NULL,
        history_operation TEXT NOT NULL CHECK(history_operation IN ('INSERT', 'UPDATE', 'DELETE')),
        history_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        history_user TEXT DEFAULT 'system'
    );
CREATE TABLE component_usage_analysis_history (
        history_id INTEGER PRIMARY KEY,
        analysis_id INTEGER NOT NULL,
        component_id INTEGER NOT NULL,
        expected_usage TEXT,
        actual_integration_status TEXT,
        missing_dependencies TEXT,
        integration_issues TEXT,
        usage_method TEXT,
        working_status TEXT,
        priority_to_fix TEXT,
        complexity_to_fix TEXT,
        current_file_paths TEXT,
        entry_points TEXT,
        dependencies_on TEXT,
        dependencies_from TEXT,
        performance_impact TEXT,
        documentation_status TEXT,
        testing_status TEXT,
        production_ready TEXT,
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL,
        created_by TEXT NOT NULL,
        is_active BOOLEAN NOT NULL,
        version INTEGER NOT NULL,
        history_operation TEXT NOT NULL CHECK(history_operation IN ('INSERT', 'UPDATE', 'DELETE')),
        history_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        history_user TEXT DEFAULT 'system'
    );
CREATE VIEW current_active_components AS
    SELECT 
        c.component_id,
        c.component_name,
        cat.category_name,
        s.status_name,
        c.file_path,
        c.priority,
        c.effort_hours,
        c.duplicated,
        c.source,
        c.notes,
        c.version,
        c.created_at,
        c.updated_at,
        c.created_by
    FROM components c
    LEFT JOIN categories cat ON c.category_id = cat.category_id
    LEFT JOIN statuses s ON c.status_id = s.status_id
    WHERE c.is_active = TRUE
    ORDER BY c.component_name
/* current_active_components(component_id,component_name,category_name,status_name,file_path,priority,effort_hours,duplicated,source,notes,version,created_at,updated_at,created_by) */;
CREATE VIEW component_change_history AS
    SELECT 
        ch.component_id,
        ch.component_name,
        ch.history_operation,
        ch.history_timestamp,
        ch.history_user,
        ch.version,
        CASE 
            WHEN ch.history_operation = 'INSERT' THEN 'Created'
            WHEN ch.history_operation = 'UPDATE' THEN 'Modified'
            WHEN ch.history_operation = 'DELETE' THEN 'Deleted'
        END as change_type
    FROM components_history ch
    ORDER BY ch.history_timestamp DESC, ch.component_id
/* component_change_history(component_id,component_name,history_operation,history_timestamp,history_user,version,change_type) */;
CREATE VIEW change_summary AS
    SELECT 
        DATE(history_timestamp) as change_date,
        history_operation,
        COUNT(*) as change_count,
        GROUP_CONCAT(DISTINCT history_user) as users_involved
    FROM components_history 
    WHERE history_timestamp >= DATE('now', '-30 days')
    GROUP BY DATE(history_timestamp), history_operation
    ORDER BY change_date DESC, history_operation
/* change_summary(change_date,history_operation,change_count,users_involved) */;
CREATE TABLE sqlite_sequence(name,seq);
CREATE VIEW component_stability_analysis AS
            SELECT 
                c.component_name,
                COUNT(DISTINCT ch.history_timestamp) as change_count,
                COUNT(DISTINCT DATE(ch.history_timestamp)) as days_with_changes,
                MIN(ch.history_timestamp) as first_change,
                MAX(ch.history_timestamp) as last_change,
                MAX(ch.version) as current_version,
                CASE 
                    WHEN COUNT(DISTINCT ch.history_timestamp) > 10 THEN 'UNSTABLE'
                    WHEN COUNT(DISTINCT ch.history_timestamp) > 5 THEN 'MODERATE'
                    ELSE 'STABLE'
                END as stability_rating,
                CASE 
                    WHEN COUNT(DISTINCT DATE(ch.history_timestamp)) > 5 THEN 'HIGH_ACTIVITY'
                    WHEN COUNT(DISTINCT DATE(ch.history_timestamp)) > 2 THEN 'MEDIUM_ACTIVITY'
                    ELSE 'LOW_ACTIVITY'
                END as activity_level
            FROM components c
            LEFT JOIN component_change_history ch ON c.component_name = ch.component_name
            WHERE c.is_active = TRUE
            GROUP BY c.component_name
            ORDER BY change_count DESC
/* component_stability_analysis(component_name,change_count,days_with_changes,first_change,last_change,current_version,stability_rating,activity_level) */;
CREATE TABLE automation_scripts (
            script_id INTEGER PRIMARY KEY,
            script_name TEXT NOT NULL UNIQUE,
            script_description TEXT,
            script_code TEXT NOT NULL,
            script_type TEXT,
            is_active BOOLEAN DEFAULT TRUE,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        , created_by TEXT DEFAULT 'insert_worker', parent_script_id INTEGER             -- NULL = top-level script

    REFERENCES automation_scripts(script_id)

    ON DELETE SET NULL

    ON UPDATE CASCADE);
CREATE TABLE file_activity_log (
            activity_id INTEGER PRIMARY KEY,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            file_path TEXT NOT NULL,
            file_name TEXT,
            change_type TEXT,
            file_size_bytes INTEGER,
            component_id INTEGER,
            is_test_file BOOLEAN DEFAULT FALSE,
            FOREIGN KEY (component_id) REFERENCES components(component_id)
        );
CREATE TABLE current_drift_alerts (
            alert_id INTEGER PRIMARY KEY,
            alert_type TEXT NOT NULL,
            severity TEXT,
            component_id INTEGER,
            alert_title TEXT NOT NULL,
            alert_description TEXT,
            detected_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            is_active BOOLEAN DEFAULT TRUE,
            FOREIGN KEY (component_id) REFERENCES components(component_id)
        );
CREATE TABLE usage_analysis_freshness_rules (
    rule_id INTEGER PRIMARY KEY AUTOINCREMENT,
    component_category TEXT NOT NULL,
    max_age_days INTEGER NOT NULL DEFAULT 30,
    requires_regular_update BOOLEAN NOT NULL DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE audit_log (
    audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
    table_name TEXT NOT NULL,
    record_id INTEGER NOT NULL,
    operation TEXT NOT NULL CHECK(operation IN ('INSERT', 'UPDATE', 'DELETE')),
    old_values TEXT, -- JSON format
    new_values TEXT, -- JSON format
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT DEFAULT 'system'
);
CREATE TABLE priority_levels (
    priority_id INTEGER PRIMARY KEY AUTOINCREMENT,
    priority_name TEXT UNIQUE NOT NULL,
    priority_order INTEGER NOT NULL, -- 1=highest, 4=lowest
    is_active BOOLEAN DEFAULT TRUE
);
CREATE TABLE complexity_levels (
    complexity_id INTEGER PRIMARY KEY AUTOINCREMENT,
    complexity_name TEXT UNIQUE NOT NULL,
    estimated_hours INTEGER, -- typical time estimate
    is_active BOOLEAN DEFAULT TRUE
);
CREATE TABLE readiness_statuses (
    readiness_id INTEGER PRIMARY KEY AUTOINCREMENT,
    readiness_name TEXT UNIQUE NOT NULL,
    readiness_description TEXT,
    is_active BOOLEAN DEFAULT TRUE
);
CREATE TABLE working_statuses (
    working_status_id INTEGER PRIMARY KEY,
    status_name TEXT NOT NULL UNIQUE,
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT NOT NULL DEFAULT 'system',
    version INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE working_statuses_history (
    history_id INTEGER PRIMARY KEY,
    working_status_id INTEGER NOT NULL,
    status_name TEXT NOT NULL,
    description TEXT,
    is_active BOOLEAN NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    created_by TEXT NOT NULL,
    version INTEGER NOT NULL,
    history_operation TEXT NOT NULL CHECK (history_operation IN ('INSERT', 'UPDATE', 'DELETE')),
    history_timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    history_user TEXT NOT NULL DEFAULT 'system'
);
CREATE TABLE usage_methods (
    usage_method_id INTEGER PRIMARY KEY,
    method_name TEXT NOT NULL UNIQUE,
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT NOT NULL DEFAULT 'system',
    version INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE usage_methods_history (
    history_id INTEGER PRIMARY KEY,
    usage_method_id INTEGER NOT NULL,
    method_name TEXT NOT NULL,
    description TEXT,
    is_active BOOLEAN NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    created_by TEXT NOT NULL,
    version INTEGER NOT NULL,
    history_operation TEXT NOT NULL CHECK (history_operation IN ('INSERT', 'UPDATE', 'DELETE')),
    history_timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    history_user TEXT NOT NULL DEFAULT 'system'
);
CREATE TABLE documentation_statuses (
    doc_status_id INTEGER PRIMARY KEY,
    status_name TEXT NOT NULL UNIQUE,
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT NOT NULL DEFAULT 'system',
    version INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE documentation_statuses_history (
    history_id INTEGER PRIMARY KEY,
    doc_status_id INTEGER NOT NULL,
    status_name TEXT NOT NULL,
    description TEXT,
    is_active BOOLEAN NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    created_by TEXT NOT NULL,
    version INTEGER NOT NULL,
    history_operation TEXT NOT NULL CHECK (history_operation IN ('INSERT', 'UPDATE', 'DELETE')),
    history_timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    history_user TEXT NOT NULL DEFAULT 'system'
);
CREATE TABLE testing_statuses (
    test_status_id INTEGER PRIMARY KEY,
    status_name TEXT NOT NULL UNIQUE,
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT NOT NULL DEFAULT 'system',
    version INTEGER NOT NULL DEFAULT 1
, scope   TEXT    DEFAULT 'total', min_pct INTEGER, max_pct INTEGER);
CREATE TABLE testing_statuses_history (
    history_id INTEGER PRIMARY KEY,
    test_status_id INTEGER NOT NULL,
    status_name TEXT NOT NULL,
    description TEXT,
    is_active BOOLEAN NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    created_by TEXT NOT NULL,
    version INTEGER NOT NULL,
    history_operation TEXT NOT NULL CHECK (history_operation IN ('INSERT', 'UPDATE', 'DELETE')),
    history_timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    history_user TEXT NOT NULL DEFAULT 'system'
, scope   TEXT, min_pct INTEGER, max_pct INTEGER);
CREATE INDEX idx_working_statuses_active ON working_statuses(is_active);
CREATE INDEX idx_usage_methods_active ON usage_methods(is_active);
CREATE INDEX idx_documentation_statuses_active ON documentation_statuses(is_active);
CREATE INDEX idx_testing_statuses_active ON testing_statuses(is_active);
CREATE INDEX idx_categories_name ON categories(category_name);
CREATE INDEX idx_categories_active ON categories(is_active);
CREATE INDEX idx_categories_created ON categories(created_at);
CREATE INDEX idx_statuses_name ON statuses(status_name);
CREATE INDEX idx_statuses_active ON statuses(is_active);
CREATE INDEX idx_statuses_created ON statuses(created_at);
CREATE INDEX idx_working_statuses_name ON working_statuses(status_name);
CREATE INDEX idx_working_statuses_created ON working_statuses(created_at);
CREATE INDEX idx_priority_levels_name ON priority_levels(priority_name);
CREATE INDEX idx_priority_levels_order ON priority_levels(priority_order);
CREATE INDEX idx_priority_levels_active ON priority_levels(is_active);
CREATE INDEX idx_complexity_levels_name ON complexity_levels(complexity_name);
CREATE INDEX idx_complexity_levels_active ON complexity_levels(is_active);
CREATE INDEX idx_complexity_levels_hours ON complexity_levels(estimated_hours);
CREATE INDEX idx_documentation_statuses_name ON documentation_statuses(status_name);
CREATE INDEX idx_documentation_statuses_created ON documentation_statuses(created_at);
CREATE INDEX idx_testing_statuses_name ON testing_statuses(status_name);
CREATE INDEX idx_testing_statuses_created ON testing_statuses(created_at);
CREATE INDEX idx_readiness_statuses_name ON readiness_statuses(readiness_name);
CREATE INDEX idx_readiness_statuses_active ON readiness_statuses(is_active);
CREATE INDEX idx_usage_methods_name ON usage_methods(method_name);
CREATE INDEX idx_usage_methods_created ON usage_methods(created_at);
CREATE INDEX idx_comp_deps_component ON component_dependencies(component_id);
CREATE INDEX idx_comp_deps_type ON component_dependencies(dependency_type);
CREATE INDEX idx_comp_deps_active ON component_dependencies(is_active);
CREATE INDEX idx_comp_deps_created ON component_dependencies(created_at);
CREATE INDEX idx_drift_alerts_type ON current_drift_alerts(alert_type);
CREATE INDEX idx_drift_alerts_severity ON current_drift_alerts(severity);
CREATE INDEX idx_drift_alerts_component ON current_drift_alerts(component_id);
CREATE INDEX idx_drift_alerts_active ON current_drift_alerts(is_active);
CREATE INDEX idx_drift_alerts_detected ON current_drift_alerts(detected_at);
CREATE INDEX idx_file_activity_component ON file_activity_log(component_id);
CREATE INDEX idx_file_activity_timestamp ON file_activity_log(timestamp);
CREATE INDEX idx_file_activity_change_type ON file_activity_log(change_type);
CREATE INDEX idx_file_activity_path ON file_activity_log(file_path);
CREATE INDEX idx_file_activity_test_file ON file_activity_log(is_test_file);
CREATE INDEX idx_audit_log_table ON audit_log(table_name);
CREATE INDEX idx_audit_log_operation ON audit_log(operation);
CREATE INDEX idx_audit_log_record ON audit_log(record_id);
CREATE INDEX idx_audit_log_created ON audit_log(created_at);
CREATE INDEX idx_categories_history_id ON categories_history(category_id);
CREATE INDEX idx_categories_history_operation ON categories_history(history_operation);
CREATE INDEX idx_categories_history_timestamp ON categories_history(history_timestamp);
CREATE INDEX idx_components_history_id ON components_history(component_id);
CREATE INDEX idx_components_history_operation ON components_history(history_operation);
CREATE INDEX idx_components_history_timestamp ON components_history(history_timestamp);
CREATE INDEX idx_statuses_history_id ON statuses_history(status_id);
CREATE INDEX idx_statuses_history_operation ON statuses_history(history_operation);
CREATE INDEX idx_statuses_history_timestamp ON statuses_history(history_timestamp);
CREATE INDEX idx_comp_usage_history_id ON component_usage_analysis_history(analysis_id);
CREATE INDEX idx_comp_usage_history_component ON component_usage_analysis_history(component_id);
CREATE INDEX idx_comp_usage_history_operation ON component_usage_analysis_history(history_operation);
CREATE INDEX idx_comp_usage_history_timestamp ON component_usage_analysis_history(history_timestamp);
CREATE TABLE IF NOT EXISTS "components" (
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
CREATE INDEX idx_components_category ON components(category_id);
CREATE INDEX idx_components_status ON components(status_id);
CREATE INDEX idx_components_name ON components(component_name);
CREATE INDEX idx_components_priority ON components(priority);
CREATE INDEX idx_components_active ON components(is_active);
CREATE INDEX idx_components_source ON components(source);
CREATE INDEX idx_components_created ON components(created_at);
CREATE TABLE IF NOT EXISTS "bug_alerts" (
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
CREATE INDEX idx_bug_alerts_type ON bug_alerts(alert_type);
CREATE INDEX idx_bug_alerts_severity ON bug_alerts(severity);
CREATE INDEX idx_bug_alerts_component ON bug_alerts(component_id);
CREATE INDEX idx_bug_alerts_active ON bug_alerts(is_active);
CREATE INDEX idx_bug_alerts_detected ON bug_alerts(detected_at);
CREATE VIEW realtime_project_health AS
SELECT
    COUNT(DISTINCT c.component_id) as total_components,
    COUNT(DISTINCT CASE WHEN fal.timestamp > datetime('now', '-7 days') THEN c.component_id END) as active_components,
    COUNT(CASE WHEN cda.is_active = TRUE THEN 1 END) as active_alerts,
    COUNT(DISTINCT fal.component_id) as components_with_file_activity,
    datetime('now') as last_updated
FROM components c
LEFT JOIN file_activity_log fal ON c.component_id = fal.component_id
LEFT JOIN current_drift_alerts cda ON c.component_id = cda.component_id
WHERE c.is_active = TRUE
/* realtime_project_health(total_components,active_components,active_alerts,components_with_file_activity,last_updated) */;
CREATE TABLE IF NOT EXISTS "component_usage_analysis" (
                analysis_id INTEGER NOT NULL,
                component_id INTEGER NOT NULL,
                expected_usage TEXT,
                missing_dependencies TEXT,
                integration_issues TEXT,
                usage_method TEXT,
                working_status TEXT,
                priority_to_fix TEXT,
                complexity_to_fix TEXT,
                current_file_paths TEXT,
                entry_points TEXT,
                dependencies_on TEXT,
                dependencies_from TEXT,
                performance_impact TEXT,
                documentation_status TEXT,
                testing_status TEXT,
                production_ready TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_by TEXT,
                is_active BOOLEAN DEFAULT TRUE,
                version INTEGER DEFAULT 1, usage_method_detail TEXT,
                FOREIGN KEY (component_id) REFERENCES components (component_id)
            );
CREATE TRIGGER sync_usage_analysis_to_components
            AFTER UPDATE OF working_status ON component_usage_analysis
            FOR EACH ROW
            WHEN NEW.working_status != OLD.working_status
            BEGIN
                UPDATE components 
                SET status_id = (
                    SELECT status_id FROM statuses 
                    WHERE status_name = NEW.working_status
                    LIMIT 1
                )
                WHERE component_id = NEW.component_id;
            END;
CREATE VIEW data_quality_report AS
    SELECT 
        'Active Components' as table_name,
        COUNT(*) as total_records,
        COUNT(CASE WHEN priority IS NULL THEN 1 END) as missing_priority,
        COUNT(CASE WHEN effort_hours IS NULL THEN 1 END) as missing_effort_hours,
        COUNT(CASE WHEN file_path IS NULL OR file_path = '' THEN 1 END) as missing_file_path,
        COUNT(CASE WHEN notes IS NULL OR notes = '' THEN 1 END) as missing_notes,
        MAX(updated_at) as last_updated
    FROM components
    WHERE is_active = TRUE
    
    UNION ALL
    
    SELECT 
        'Usage Analysis' as table_name,
        COUNT(*) as total_records,
        COUNT(CASE WHEN priority_to_fix IS NULL THEN 1 END) as missing_priority_to_fix,
        COUNT(CASE WHEN complexity_to_fix IS NULL THEN 1 END) as missing_complexity,
        COUNT(CASE WHEN missing_dependencies IS NULL THEN 1 END) as missing_deps_info,
        COUNT(CASE WHEN production_ready IS NULL THEN 1 END) as missing_prod_ready,
        MAX(updated_at) as last_updated
    FROM component_usage_analysis
    WHERE is_active = TRUE
/* data_quality_report(table_name,total_records,missing_priority,missing_effort_hours,missing_file_path,missing_notes,last_updated) */;
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
WHERE ua.is_active = TRUE
/* stale_usage_analysis(component_id,component_name,category_name,updated_at,max_age_days,days_since_update,freshness_status) */;
CREATE TRIGGER sync_working_status_to_components
            AFTER UPDATE OF working_status ON component_usage_analysis
            FOR EACH ROW
            WHEN NEW.working_status IS NOT NULL AND NEW.working_status != OLD.working_status
            BEGIN
                -- Update components.status_id by finding matching status_name
                UPDATE components 
                SET status_id = (
                    SELECT status_id FROM statuses 
                    WHERE status_name = NEW.working_status
                    LIMIT 1
                ),
                updated_at = CURRENT_TIMESTAMP
                WHERE component_id = NEW.component_id;
            END;
CREATE TRIGGER trg_test_status_ad

AFTER DELETE ON testing_statuses

BEGIN

  INSERT INTO testing_statuses_history

  VALUES (OLD.test_status_id, OLD.status_name, OLD.description, OLD.is_active,

          OLD.created_at, OLD.updated_at, OLD.created_by, OLD.version,

          'DELETE', datetime('now'), COALESCE(OLD.created_by,'system'));

END;
CREATE TRIGGER trg_test_status_au

AFTER UPDATE ON testing_statuses

BEGIN

  INSERT INTO testing_statuses_history

        (test_status_id, status_name, description, is_active,

         created_at, updated_at, created_by, version,

         history_operation, history_timestamp, history_user)

  VALUES (NEW.test_status_id, NEW.status_name, NEW.description, NEW.is_active,

          NEW.created_at, NEW.updated_at, NEW.created_by, NEW.version,

          'UPDATE', datetime('now'), COALESCE(NEW.created_by,'system'));

END;
CREATE TRIGGER trg_test_status_ai

AFTER INSERT ON testing_statuses

BEGIN

  INSERT INTO testing_statuses_history

        (test_status_id, status_name, description, is_active,

         created_at, updated_at, created_by, version,

         scope, min_pct, max_pct,

         history_operation, history_timestamp, history_user)

  VALUES (NEW.test_status_id, NEW.status_name, NEW.description, NEW.is_active,

          NEW.created_at, NEW.updated_at, NEW.created_by, NEW.version,

          NEW.scope, NEW.min_pct, NEW.max_pct,

          'INSERT', datetime('now'), COALESCE(NEW.created_by,'system'));

END;
CREATE TRIGGER trg_work_status_ai

AFTER INSERT ON working_statuses

BEGIN

  INSERT INTO working_statuses_history

        (working_status_id,status_name,description,is_active,

         created_at,updated_at,created_by,version,

         history_operation,history_timestamp,history_user)

  VALUES (NEW.working_status_id,NEW.status_name,NEW.description,NEW.is_active,

          NEW.created_at,NEW.updated_at,NEW.created_by,NEW.version,

          'INSERT',datetime('now'),COALESCE(NEW.created_by,'system'));

END;
CREATE TRIGGER trg_work_status_au

AFTER UPDATE ON working_statuses

BEGIN

  INSERT INTO working_statuses_history

        (working_status_id,status_name,description,is_active,

         created_at,updated_at,created_by,version,

         history_operation,history_timestamp,history_user)

  VALUES (NEW.working_status_id,NEW.status_name,NEW.description,NEW.is_active,

          NEW.created_at,NEW.updated_at,NEW.created_by,NEW.version,

          'UPDATE',datetime('now'),COALESCE(NEW.created_by,'system'));

END;
CREATE TRIGGER trg_work_status_ad

AFTER DELETE ON working_statuses

BEGIN

  INSERT INTO working_statuses_history

        (working_status_id,status_name,description,is_active,

         created_at,updated_at,created_by,version,

         history_operation,history_timestamp,history_user)

  VALUES (OLD.working_status_id,OLD.status_name,OLD.description,OLD.is_active,

          OLD.created_at,OLD.updated_at,OLD.created_by,OLD.version,

          'DELETE',datetime('now'),COALESCE(OLD.created_by,'system'));

END;
CREATE TRIGGER trg_cua_chk_working_status_ins

BEFORE INSERT ON component_usage_analysis

WHEN NEW.working_status NOT IN (

       'Fully Working','Partially Working','Missing','Broken',

       'Exists But Not Connected','Blocked by missing service layer',

       'Duplicated','Unknown'

     )

BEGIN

  SELECT RAISE(ABORT, 'Invalid working_status');

END;
CREATE TRIGGER trg_cua_chk_working_status_upd

BEFORE UPDATE ON component_usage_analysis

WHEN NEW.working_status NOT IN (

       'Fully Working','Partially Working','Missing','Broken',

       'Exists But Not Connected','Blocked by missing service layer',

       'Duplicated','Unknown'

     )

BEGIN

  SELECT RAISE(ABORT, 'Invalid working_status');

END;
CREATE TRIGGER trg_cua_chk_testing_status_ins

BEFORE INSERT ON component_usage_analysis

WHEN NEW.testing_status NOT IN (

       'No Tests','Smoke Tests Only',

       'Unit ΓÇô Low Coverage','Unit ΓÇô Medium Coverage','Unit ΓÇô High Coverage',

       'Integration ΓÇô Partial','Integration ΓÇô Comprehensive',

       'Full Coverage','Tests Failing'

     )

BEGIN

  SELECT RAISE(ABORT, 'Invalid testing_status');

END;
CREATE TRIGGER trg_cua_chk_testing_status_upd

BEFORE UPDATE ON component_usage_analysis

WHEN NEW.testing_status NOT IN (

       'No Tests','Smoke Tests Only',

       'Unit ΓÇô Low Coverage','Unit ΓÇô Medium Coverage','Unit ΓÇô High Coverage',

       'Integration ΓÇô Partial','Integration ΓÇô Comprehensive',

       'Full Coverage','Tests Failing'

     )

BEGIN

  SELECT RAISE(ABORT, 'Invalid testing_status');

END;
CREATE TRIGGER trg_cua_chk_usage_method_ins

BEFORE INSERT ON component_usage_analysis

WHEN NEW.usage_method NOT IN (

  'Method needs documentation','Direct Import','Factory Pattern','Dependency Injection',

  'API Endpoint','CLI Command','Event Handler','Configuration',

  'WebSocket Endpoint','Background Worker','Scheduled Task','Batch Job',

  'Message Queue Consumer','Message Queue Producer','Stream Processor',

  'REST Client','gRPC Service','GraphQL Query','Plugin System',

  'Middleware','SDK / Library Call'

)

BEGIN SELECT RAISE(ABORT,'Invalid usage_method'); END;
CREATE TRIGGER trg_cua_chk_usage_method_upd

BEFORE UPDATE ON component_usage_analysis

WHEN NEW.usage_method NOT IN (

  'Method needs documentation','Direct Import','Factory Pattern','Dependency Injection',

  'API Endpoint','CLI Command','Event Handler','Configuration',

  'WebSocket Endpoint','Background Worker','Scheduled Task','Batch Job',

  'Message Queue Consumer','Message Queue Producer','Stream Processor',

  'REST Client','gRPC Service','GraphQL Query','Plugin System',

  'Middleware','SDK / Library Call'

)

BEGIN SELECT RAISE(ABORT,'Invalid usage_method'); END;
CREATE TRIGGER trg_cua_chk_doc_status_ins

BEFORE INSERT ON component_usage_analysis

WHEN NEW.documentation_status NOT IN (

  'Needs documentation review',

  'Not Documented',

  'Partially Documented',

  'Fully Documented',

  'Documentation Outdated'

)

BEGIN SELECT RAISE(ABORT,'Invalid documentation_status'); END;
CREATE TRIGGER trg_cua_chk_doc_status_upd

BEFORE UPDATE ON component_usage_analysis

WHEN NEW.documentation_status NOT IN (

  'Needs documentation review',

  'Not Documented',

  'Partially Documented',

  'Fully Documented',

  'Documentation Outdated'

)

BEGIN SELECT RAISE(ABORT,'Invalid documentation_status'); END;
CREATE TRIGGER trg_cua_autofill_usage_detail_ins

AFTER INSERT ON component_usage_analysis

FOR EACH ROW

WHEN NEW.usage_method_detail IS NULL

   OR trim(NEW.usage_method_detail) = ''

BEGIN

  UPDATE component_usage_analysis

  SET    usage_method_detail = NEW.usage_method,

         updated_at          = datetime('now')

  WHERE  rowid = NEW.rowid;

END;
CREATE TRIGGER trg_cua_autofill_usage_detail_upd

AFTER UPDATE ON component_usage_analysis

FOR EACH ROW

WHEN NEW.usage_method_detail IS NULL

   OR trim(NEW.usage_method_detail) = ''

BEGIN

  UPDATE component_usage_analysis

  SET    usage_method_detail = NEW.usage_method,

         updated_at          = datetime('now')

  WHERE  rowid = NEW.rowid;

END;
CREATE TRIGGER trg_cua_chk_priority_ins

BEFORE INSERT ON component_usage_analysis

WHEN NEW.priority_to_fix NOT IN ('Critical','High','Medium','Low')

BEGIN

  SELECT RAISE(ABORT,'Invalid priority_to_fix');

END;
CREATE TRIGGER trg_cua_chk_priority_upd

BEFORE UPDATE OF priority_to_fix ON component_usage_analysis

WHEN NEW.priority_to_fix NOT IN ('Critical','High','Medium','Low')

BEGIN

  SELECT RAISE(ABORT,'Invalid priority_to_fix');

END;
CREATE TRIGGER trg_cua_chk_complexity_ins

BEFORE INSERT ON component_usage_analysis

WHEN NEW.complexity_to_fix NOT IN ('Easy','Medium','Hard','Very Hard')

BEGIN

  SELECT RAISE(ABORT,'Invalid complexity_to_fix');

END;
CREATE TRIGGER trg_cua_chk_complexity_upd

BEFORE UPDATE OF complexity_to_fix ON component_usage_analysis

WHEN NEW.complexity_to_fix NOT IN ('Easy','Medium','Hard','Very Hard')

BEGIN

  SELECT RAISE(ABORT,'Invalid complexity_to_fix');

END;
CREATE TRIGGER trg_cua_production_ready_guard

BEFORE UPDATE OF production_ready ON component_usage_analysis

WHEN NEW.production_ready IS NOT OLD.production_ready

  AND NEW.created_by NOT LIKE 'system:%'

BEGIN

  SELECT RAISE(ABORT,'production_ready may only be changed by system processes');

END;
CREATE TABLE llm_write_queue (

    queue_id      INTEGER PRIMARY KEY AUTOINCREMENT,

    target_table  TEXT    NOT NULL

                  CHECK (target_table = 'component_usage_analysis'),

    op_type       TEXT    NOT NULL CHECK (op_type IN ('INSERT','UPDATE')),

    payload_json  TEXT    NOT NULL CHECK (json_valid(payload_json)),

    created_by    TEXT    DEFAULT 'llm:auto',

    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP

, status TEXT NOT NULL

        DEFAULT 'pending'

        CHECK (status IN ('pending','applied','error')), error_msg    TEXT, processed_at DATETIME);
CREATE UNIQUE INDEX uq_cua_analysis_id

    ON component_usage_analysis (analysis_id);
CREATE TABLE git_activity_log (

    activity_id       INTEGER PRIMARY KEY,

    timestamp         DATETIME      DEFAULT CURRENT_TIMESTAMP,

    file_path         TEXT          NOT NULL,

    file_name         TEXT,

    change_type       TEXT,

    file_size_bytes   INTEGER,

    component_id      INTEGER,

    is_test_file      BOOLEAN       DEFAULT FALSE,

    FOREIGN KEY (component_id) REFERENCES components(component_id)

);
CREATE INDEX idx_git_activity_timestamp   ON git_activity_log(timestamp);
CREATE INDEX idx_git_activity_change_type ON git_activity_log(change_type);
CREATE INDEX idx_git_activity_component   ON git_activity_log(component_id);
CREATE INDEX idx_git_activity_path        ON git_activity_log(file_path);
CREATE UNIQUE INDEX ux_git_activity_unique

      ON git_activity_log (timestamp, file_path, change_type);
CREATE TABLE automation_scripts_history (

    history_id        INTEGER PRIMARY KEY AUTOINCREMENT,

    script_id         INTEGER NOT NULL,

    script_name       TEXT    NOT NULL,

    script_description TEXT,

    script_code       TEXT    NOT NULL,

    script_type       TEXT,

    is_active         BOOLEAN NOT NULL,

    created_at        DATETIME NOT NULL,

    -- --- history meta ---

    history_operation TEXT    NOT NULL           /* 'INSERT' | 'UPDATE' | 'DELETE' */,

    history_timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    history_user      TEXT    NOT NULL DEFAULT 'system'

);
CREATE INDEX idx_auto_scripts_hist_ts

       ON automation_scripts_history(history_timestamp);
CREATE TRIGGER trg_auto_scripts_ai

AFTER INSERT ON automation_scripts

BEGIN

    INSERT INTO automation_scripts_history

          (script_id, script_name, script_description, script_code,

           script_type, is_active, created_at,

           history_operation, history_timestamp, history_user)

    VALUES (NEW.script_id, NEW.script_name, NEW.script_description, NEW.script_code,

            NEW.script_type, NEW.is_active, NEW.created_at,

            'INSERT', datetime('now'), COALESCE(NEW.created_by,'system'));

END;
CREATE TRIGGER trg_auto_scripts_au

AFTER UPDATE ON automation_scripts

BEGIN

    INSERT INTO automation_scripts_history

          (script_id, script_name, script_description, script_code,

           script_type, is_active, created_at,

           history_operation, history_timestamp, history_user)

    VALUES (NEW.script_id, NEW.script_name, NEW.script_description, NEW.script_code,

            NEW.script_type, NEW.is_active, NEW.created_at,

            'UPDATE', datetime('now'), COALESCE(NEW.created_by,'system'));

END;
CREATE TRIGGER trg_auto_scripts_ad

AFTER DELETE ON automation_scripts

BEGIN

    INSERT INTO automation_scripts_history

          (script_id, script_name, script_description, script_code,

           script_type, is_active, created_at,

           history_operation, history_timestamp, history_user)

    VALUES (OLD.script_id, OLD.script_name, OLD.script_description, OLD.script_code,

            OLD.script_type, OLD.is_active, OLD.created_at,

            'DELETE', datetime('now'), COALESCE(OLD.created_by,'system'));

END;
CREATE TRIGGER trg_auto_scripts_hist_prune

AFTER INSERT ON automation_scripts_history

BEGIN

    /* delete everything **except** the newest 1 000 rows            */

    DELETE FROM automation_scripts_history

    WHERE history_id IN (

        SELECT history_id

        FROM   automation_scripts_history

        ORDER  BY history_timestamp DESC   -- newest ΓåÆ oldest

        LIMIT -1 OFFSET 1000               -- skip first 1 000

    );

END;
CREATE TRIGGER trg_file_activity_git_redirect

BEFORE INSERT ON file_activity_log

WHEN  lower(NEW.file_path) LIKE '%/.git/%'

   OR lower(NEW.file_path) LIKE '%\.git\%'          -- Windows slashes

BEGIN

    /* copy ΓåÆ git table   (OR IGNORE prevents dup-error) */

    INSERT OR IGNORE INTO git_activity_log

          (timestamp, file_path, file_name,

           change_type, file_size_bytes, component_id, is_test_file)

    VALUES (NEW.timestamp, NEW.file_path, NEW.file_name,

            NEW.change_type, NEW.file_size_bytes,

            NEW.component_id, NEW.is_test_file);



    /* cancel the original insert */

    SELECT RAISE(IGNORE);

END;
CREATE TRIGGER trg_git_activity_path_check

BEFORE INSERT ON git_activity_log

WHEN  lower(NEW.file_path) NOT LIKE '%/.git/%'

   AND lower(NEW.file_path) NOT LIKE '%\.git\%'

BEGIN

    SELECT RAISE(ABORT,

        'file_activity_log only: path is not under a .git directory');

END;
CREATE VIEW v_activity_cutoff AS

SELECT datetime('now', '-90 days') AS cutoff
/* v_activity_cutoff(cutoff) */;
CREATE VIEW v_activity_keep_rowids AS

WITH cutoff AS (SELECT cutoff FROM v_activity_cutoff)



SELECT rowid

FROM (



    /* ===== file_activity_log ===== */



    /* inside 90 d ΓÇô keep Γëñ 10 000 */

    SELECT

        rowid,

        ROW_NUMBER() OVER (

            PARTITION BY file_path, change_type

            ORDER BY timestamp DESC

        )            AS rn,

        10000        AS keep_cap

    FROM file_activity_log

    WHERE timestamp >= (SELECT cutoff FROM cutoff)



    UNION ALL



    /* outside 90 d ΓÇô keep Γëñ 1 000 */

    SELECT

        rowid,

        ROW_NUMBER() OVER (

            PARTITION BY file_path, change_type

            ORDER BY timestamp DESC

        )            AS rn,

        1000         AS keep_cap

    FROM file_activity_log

    WHERE timestamp < (SELECT cutoff FROM cutoff)



    /* ===== git_activity_log ===== */



    UNION ALL



    /* inside 90 d ΓÇô keep Γëñ 10 000 */

    SELECT

        rowid,

        ROW_NUMBER() OVER (

            PARTITION BY file_path, change_type

            ORDER BY timestamp DESC

        )            AS rn,

        10000        AS keep_cap

    FROM git_activity_log

    WHERE timestamp >= (SELECT cutoff FROM cutoff)



    UNION ALL



    /* outside 90 d ΓÇô keep Γëñ 1 000 */

    SELECT

        rowid,

        ROW_NUMBER() OVER (

            PARTITION BY file_path, change_type

            ORDER BY timestamp DESC

        )            AS rn,

        1000         AS keep_cap

    FROM git_activity_log

    WHERE timestamp < (SELECT cutoff FROM cutoff)



)

/* keep only rows that meet their per-file cap */

WHERE rn <= keep_cap
/* v_activity_keep_rowids(rowid) */;
CREATE TRIGGER trg_file_activity_prune

AFTER INSERT ON file_activity_log

BEGIN

    /* delete any rows for this file+change_type that

       are no longer part of the keep list               */

    DELETE FROM file_activity_log

    WHERE rowid NOT IN (SELECT rowid FROM v_activity_keep_rowids)

      AND file_path  = NEW.file_path

      AND change_type = NEW.change_type;

END;
CREATE TRIGGER trg_git_activity_prune

AFTER INSERT ON git_activity_log

BEGIN

    DELETE FROM git_activity_log

    WHERE rowid NOT IN (SELECT rowid FROM v_activity_keep_rowids)

      AND file_path  = NEW.file_path

      AND change_type = NEW.change_type;

END;
CREATE TRIGGER trg_issues_hist_prune

AFTER INSERT ON component_issues_history

BEGIN

    /* delete everything except the newest 1 000 rows */

    DELETE FROM component_issues_history

     WHERE rowid NOT IN (

           SELECT rowid

             FROM component_issues_history

         ORDER BY history_timestamp DESC   -- newest first

            LIMIT 1000

         );

END;
CREATE TRIGGER trg_cua_block_fully_working

BEFORE UPDATE OF working_status             -- fires only when working_status changes

ON component_usage_analysis

FOR EACH ROW

WHEN NEW.working_status = 'Fully Working'

     AND                                   -- ΓÇªand there is at least one open issue

     EXISTS (

         SELECT 1

         FROM   "component_issues_old" ci

         WHERE  ci.component_id = NEW.component_id

           AND  ci.resolved     = 0

           AND  ci.is_active    = 1

     )

BEGIN

    SELECT RAISE(ABORT,

        'Cannot set to Fully Working ΓÇô unresolved issues exist for this component');

END;
CREATE TRIGGER trg_components_block_fully_working

BEFORE UPDATE OF status_id

ON components

FOR EACH ROW

WHEN

    (SELECT status_name                -- translate the new status_id

       FROM statuses

      WHERE status_id = NEW.status_id) = 'Fully Working'

    AND EXISTS (                       -- open issues?

        SELECT 1

        FROM   "component_issues_old" ci

        WHERE  ci.component_id = NEW.component_id

          AND  ci.resolved     = 0

          AND  ci.is_active    = 1

    )

BEGIN

    SELECT RAISE(ABORT,

        'Cannot mark component Fully Working ΓÇô unresolved issues exist');

END;
CREATE VIEW file_activity_summary AS
        SELECT 
            date(timestamp) as activity_date,
            COUNT(*) as total_changes,
            COUNT(DISTINCT file_path) as files_changed,
            COUNT(CASE WHEN change_type = 'created' THEN 1 END) as files_created,
            COUNT(CASE WHEN change_type = 'modified' THEN 1 END) as edits_made,
            COUNT(CASE WHEN is_test_file = TRUE THEN 1 END) as test_changes
        FROM file_activity_log 
        WHERE timestamp > datetime('now', '-30 days')
        GROUP BY date(timestamp)
        ORDER BY activity_date DESC
/* file_activity_summary(activity_date,total_changes,files_changed,files_created,edits_made,test_changes) */;
CREATE VIEW usage_analysis_quality_issues AS
            SELECT
                ua.component_id,
                c.component_name,
                CASE
                    WHEN length(ua.expected_usage) < 20 THEN 'Short expected_usage'
                    WHEN length(ua.working_status) < 10 THEN 'Short working_status'
                    WHEN length(ua.usage_method) < 10 THEN 'Short usage_method'
                    WHEN length(ua.current_file_paths) < 10 THEN 'Short file_paths'

                    WHEN ua.usage_method_detail = 'Method needs documentation' THEN 'Usage method not documented'
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
                length(ua.working_status) < 10 OR
                length(ua.usage_method) < 10 OR
                length(ua.current_file_paths) < 10 OR

                ua.usage_method_detail = 'Method needs documentation' OR
                ua.working_status = 'Unknown' OR
                ua.production_ready = 'Unknown'
              )
/* usage_analysis_quality_issues(component_id,component_name,quality_issue,updated_at) */;
CREATE TRIGGER trg_llm_queue_status_guard

BEFORE UPDATE OF status ON llm_write_queue

WHEN NEW.status <> OLD.status

  AND NEW.status NOT IN ('error','applied')

BEGIN

  SELECT RAISE(ABORT,'status may only transition to applied|error');

END;
CREATE TRIGGER trg_llm_queue_basic_check

BEFORE INSERT ON llm_write_queue

WHEN json_type(NEW.payload_json) IS NULL          /* malformed JSON */

   OR NEW.target_table NOT IN (

        'component_usage_analysis',

        'component_issues',

        'component_dependencies')

   OR NEW.op_type       NOT IN ('INSERT','UPDATE')

BEGIN

  SELECT RAISE(ABORT,'Invalid queue row');

END;
CREATE TABLE issue_types (

    issue_type TEXT PRIMARY KEY,

    is_active  BOOLEAN DEFAULT 1

);
CREATE TABLE component_issues (

    issue_id       INTEGER PRIMARY KEY,

    component_id   INTEGER NOT NULL REFERENCES components(component_id) ON DELETE CASCADE,

    issue_description TEXT NOT NULL,

    severity       TEXT NOT NULL,                     -- keep existing enum / CHECK

    resolved       BOOLEAN DEFAULT 0,

    created_at     DATETIME DEFAULT CURRENT_TIMESTAMP,

    updated_at     DATETIME DEFAULT CURRENT_TIMESTAMP,

    resolved_at    DATETIME,

    created_by     TEXT,

    resolved_by    TEXT,

    is_active      BOOLEAN DEFAULT 1,

    issue_type     TEXT NOT NULL REFERENCES issue_types(issue_type),

    external_reference TEXT

);
CREATE TRIGGER trg_components_auto_stub

AFTER INSERT ON components

BEGIN

  /* stub issue */

  INSERT INTO component_issues (

        component_id, issue_description, severity,

        issue_type, resolved, is_active, created_by

  ) VALUES (

        NEW.component_id,

        'None recorded',

        'None',

        'none_recorded',

        1,               -- resolved = true

        1,

        'auto_stub'

  );



  /* stub dependency (assumes dependency_types table already has none_recorded) */

  INSERT INTO component_dependencies (

        component_id, depends_on, dependency_type,

        is_active, created_by

  ) VALUES (

        NEW.component_id,

        'None recorded',

        'none_recorded',

        1,

        'auto_stub'

  );

END;
CREATE TABLE issue_match_map (

    pattern      TEXT PRIMARY KEY,   -- GLOB/LIKE pattern, lowercase

    target_type  TEXT NOT NULL       -- FK to issue_types

);
CREATE VIEW priority_dashboard AS

WITH

  /* lookup weights ---------------------------------------------------------*/

  status_w(key,val) AS (

      VALUES ('Fully Working',0.90),

             ('Partially Working',0.60),

             ('Exists But Not Connected',0.50),

             ('Duplicated',0.40),

             ('Missing',0.10),

             ('Broken',0.00)

  ),

  doc_w(key,val) AS (

      VALUES ('Fully Documented',1.00),

             ('Partially Documented',0.60),

             ('Documentation Outdated',0.40),

             ('Not Documented',0.10)

  ),

  test_w(key,val) AS (

      VALUES ('Unit ΓÇô High Coverage',1.00),

             ('Full Coverage',1.00),

             ('Integration ΓÇô Comprehensive',0.90),

             ('Unit ΓÇô Medium Coverage',0.70),

             ('Integration ΓÇô Partial',0.60),

             ('Smoke Tests Only',0.40),

             ('Unit ΓÇô Low Coverage',0.40),

             ('Tests Failing',0.20),

             ('No Tests',0.10)

  ),

  ready_w(key,val) AS (VALUES ('Yes',1.00),('Partial',0.50),('No',0.10)),



  /* open-issue count -------------------------------------------------------*/

  issues AS (

      SELECT component_id, COUNT(*) AS open_cnt

      FROM   "component_issues"

      WHERE  is_active = 1 AND resolved = 0

      GROUP  BY component_id

  ),



  /* raw metrics ------------------------------------------------------------*/

  raw AS (

      SELECT

          c.component_id,

          c.component_name,

          s.status_name,

          c.priority,

          ua.documentation_status,

          ua.testing_status,

          ua.production_ready,

          COALESCE(i.open_cnt,0)              AS open_issues,

          sw.val                              AS status_score,

          dw.val                              AS doc_score,

          tw.val                              AS test_score,

          CASE WHEN COALESCE(i.open_cnt,0)=0 THEN 1.0 ELSE 0.0 END

                                             AS issue_score,

          rw.val                              AS ready_score,

          c.effort_hours,

          /* 7-day activity buckets */

          CASE

            WHEN (SELECT COUNT(*) FROM file_activity_log fal

                  WHERE fal.component_id = c.component_id

                    AND fal.timestamp > datetime('now','-7 day')) > 10

                 THEN 'Very Active'

            WHEN (SELECT COUNT(*) FROM file_activity_log fal

                  WHERE fal.component_id = c.component_id

                    AND fal.timestamp > datetime('now','-7 day')) > 3

                 THEN 'Active'

            WHEN (SELECT COUNT(*) FROM file_activity_log fal

                  WHERE fal.component_id = c.component_id

                    AND fal.timestamp > datetime('now','-7 day')) > 0

                 THEN 'Some Activity'

            ELSE 'Inactive'

          END                                   AS activity_level,

          CASE

            WHEN ua.testing_status IN ('Unit ΓÇô High Coverage',

                                       'Full Coverage',

                                       'Integration ΓÇô Comprehensive')

                 THEN 'Has Tests'

            ELSE 'No Tests'

          END                                   AS test_coverage_status,

          c.updated_at                          AS last_updated

      FROM  components                c

      JOIN  statuses                  s  ON s.status_id     = c.status_id

      JOIN  component_usage_analysis  ua ON ua.component_id = c.component_id

      JOIN  status_w sw ON sw.key = s.status_name

      JOIN  doc_w    dw ON dw.key = ua.documentation_status

      JOIN  test_w   tw ON tw.key = ua.testing_status

      JOIN  ready_w  rw ON rw.key = ua.production_ready

      LEFT JOIN issues i ON i.component_id = c.component_id

      WHERE c.is_active = 1 AND ua.is_active = 1

  ),



  /* ΓåÉΓÇòΓÇò HEREΓÇÖS THE COMMA THAT WAS MISSING --------------------*/

  scored AS (

      SELECT

          component_id,

          component_name,

          status_name,

          priority,

          documentation_status,

          testing_status,

          production_ready,

          open_issues,

          effort_hours,

          activity_level,

          test_coverage_status,

          last_updated,

          ROUND(

             (0.30*status_score +

              0.20*doc_score   +

              0.20*test_score  +

              0.15*issue_score +

              0.15*ready_score) * 100 , 1

          ) AS completion_percentage,

          status_score, doc_score, test_score, issue_score, ready_score

      FROM raw

  )

SELECT

    component_name,

    status_name AS status,

    priority,

    completion_percentage,



    /* --------- new reason compiler ---------- */

    TRIM(

         /* 1∩╕ÅΓâú unresolved issues first (if any) */

         CASE WHEN open_issues > 0

              THEN 'Open Issues; ' ELSE '' END ||



         /* 2∩╕ÅΓâú status, docs, tests, prod-ready    */

         CASE WHEN status_score < 1

              THEN 'Status '||status_name||'; ' ELSE '' END ||

         CASE WHEN doc_score   < 1

              THEN 'Docs '||documentation_status||'; ' ELSE '' END ||

         CASE WHEN test_score  < 1

              THEN 'Tests '||testing_status||'; ' ELSE '' END ||

         CASE WHEN ready_score < 1

              THEN 'ProdReady '||production_ready||'; ' ELSE '' END,



         ' ;'                -- strip trailing ΓÇ£; ΓÇ¥ or space

    ) AS incomplete_reasons,



    effort_hours,

    activity_level,

    test_coverage_status,

    last_updated

FROM scored

ORDER BY

  CASE priority

       WHEN 'Critical' THEN 1

       WHEN 'High'     THEN 2

       WHEN 'Medium'   THEN 3

       WHEN 'Low'      THEN 4

       ELSE 5 END,

  completion_percentage ASC,

  component_name
/* priority_dashboard(component_name,status,priority,completion_percentage,incomplete_reasons,effort_hours,activity_level,test_coverage_status,last_updated) */;
CREATE TABLE dependency_types (

    dependency_type TEXT PRIMARY KEY,

    is_active       BOOLEAN DEFAULT 1

);
CREATE VIEW critical_blockers AS

SELECT 

    co.component_name,

    co.category_name,

    co.status_name,

    ua.working_status,

    ua.priority_to_fix,

    ua.missing_dependencies,

    ua.integration_issues,

    ua.complexity_to_fix,

    co.effort_hours,

    co.source,

    co.version,

    co.updated_at AS last_updated

FROM   current_active_components     co

LEFT   JOIN component_usage_analysis ua

       ON ua.component_id = co.component_id

/* unresolved HIGH / CRITICAL issues for this component */

LEFT   JOIN (

       SELECT component_id,

              1 AS has_blocking_issue

       FROM   "component_issues"

       WHERE  is_active = 1

         AND  resolved   = 0

         AND  severity  IN ('High','Critical')

       GROUP  BY component_id

) ci ON ci.component_id = co.component_id

WHERE (

        ua.priority_to_fix = 'CRITICAL'              -- already-existing rules

     OR co.status_name    IN ('Missing','Broken')

     OR ua.working_status IN ('Missing','Broken')

     OR ci.has_blocking_issue = 1                    -- ΓåÉ NEW rule

)

  AND ua.is_active = 1

ORDER BY

    /* Bring CRITICAL priority or unresolved CRITICAL issues to the top */

    CASE 

        WHEN ci.has_blocking_issue = 1 THEN 0         -- unresolved High/Critical issue

        WHEN ua.priority_to_fix   = 'CRITICAL' THEN 1

        WHEN ua.priority_to_fix   = 'HIGH'      THEN 2

        ELSE 3

    END,

    co.effort_hours ASC
/* critical_blockers(component_name,category_name,status_name,working_status,priority_to_fix,missing_dependencies,integration_issues,complexity_to_fix,effort_hours,source,version,last_updated) */;
CREATE VIEW bug_detection_report AS

/* ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ */

/* 1.  Broken components                                     */

SELECT

    'BROKEN_COMPONENT' AS alert_type,

    'CRITICAL'         AS severity,

    c.component_name,

    'Component marked as BROKEN - requires immediate attention. ' ||

    'Priority: ' || c.priority || ', Effort: ' || c.effort_hours || 'h'

                      AS description,

    'BROKEN_STATUS'    AS bug_category,

    datetime('now')    AS detected_at

FROM   components c

JOIN   statuses   s ON c.status_id = s.status_id

WHERE  c.is_active = 1

  AND  s.status_name = 'Broken'



UNION ALL

/* 2.  Status mismatches                                     */

SELECT

    'DATA_INCONSISTENCY',

    'HIGH',

    c.component_name,

    'Status mismatch: components.status (' || s.status_name ||

    ') vs usage_analysis.working_status (' || ua.working_status || ')' ,

    'MISMATCH_STATUS',

    datetime('now')

FROM   components c

JOIN   statuses   s  ON c.status_id = s.status_id

JOIN   component_usage_analysis ua ON c.component_id = ua.component_id

WHERE  ua.is_active = 1

  AND  c.is_active  = 1

  AND ((s.status_name = 'Fully Working' AND ua.working_status != 'Fully Working')

       OR (s.status_name != 'Fully Working' AND ua.working_status = 'Fully Working'))



UNION ALL

/* 3.  Effort-hours mismatch (FW but hours > 0)              */

SELECT

    'EFFORT_HOURS_INCONSISTENCY',

    'MEDIUM',

    c.component_name,

    'Logic error: marked as "Fully Working" but still has ' ||

    c.effort_hours || ' effort hours remaining',

    'EFFORT_LOGIC_ERROR',

    datetime('now')

FROM   components c

JOIN   statuses   s ON c.status_id = s.status_id

WHERE  c.is_active = 1

  AND  s.status_name = 'Fully Working'

  AND  c.effort_hours > 0



UNION ALL

/* 4.  Priority / status logic errors                        */

SELECT

    'LOGIC_INCONSISTENCY',

    'MEDIUM',

    c.component_name,

    'Logic error: marked as "' || ua.working_status ||

    '" but priority is ' || ua.priority_to_fix,

    'PRIORITY_LOGIC',

    datetime('now')

FROM   components c

JOIN   component_usage_analysis ua ON c.component_id = ua.component_id

WHERE  ua.is_active = 1

  AND  c.is_active  = 1

  AND ((ua.working_status = 'Fully Working' AND ua.priority_to_fix IN ('HIGH','CRITICAL'))

       OR (ua.working_status IN ('Broken','Missing') AND ua.priority_to_fix = 'LOW'))



UNION ALL

/* 5.  Missing critical dependencies                         */

SELECT

    'MISSING_DEPENDENCY',

    'HIGH',

    c.component_name,

    'Critical component missing: ' || ua.missing_dependencies,

    'DEPENDENCY_MISSING',

    datetime('now')

FROM   components c

JOIN   component_usage_analysis ua ON c.component_id = ua.component_id

WHERE  ua.is_active = 1

  AND  c.is_active  = 1

  AND  ua.working_status = 'Broken'

  AND  ua.missing_dependencies LIKE '%missing%'

  AND  ua.priority_to_fix IN ('HIGH','CRITICAL')



UNION ALL

/* 6.  Effort/complexity mismatch   (exclude FW)             */

SELECT

    'EFFORT_LOGIC',

    'LOW',

    c.component_name,

    'Effort hours (' || COALESCE(c.effort_hours,0) || 'h) seems inconsistent with complexity (' ||

    ua.complexity_to_fix || ')',

    'EFFORT_MISMATCH',

    datetime('now')

FROM   components c

JOIN   component_usage_analysis ua ON c.component_id = ua.component_id

JOIN   statuses s  ON c.status_id = s.status_id

WHERE  ua.is_active = 1

  AND  c.is_active  = 1

  AND  s.status_name != 'Fully Working'

  AND ((ua.complexity_to_fix = 'Hard'  AND COALESCE(c.effort_hours,0) < 8)

       OR (ua.complexity_to_fix = 'Easy' AND COALESCE(c.effort_hours,0) > 16))



UNION ALL

/* 7.  Stale components (no update > 30 days)                */

SELECT

    'STALE_COMPONENT',

    'INFO',

    c.component_name,

    'Component not updated in over 30 days (last: ' || c.updated_at || ')',

    'STALE_DATA',

    datetime('now')

FROM   components c

WHERE  c.is_active = 1

  AND  julianday('now') - julianday(c.updated_at) > 30

  AND  c.component_name NOT LIKE '%Test%'



UNION ALL

/* 8.  Production-ready but not FW                           */

SELECT

    'PRODUCTION_ISSUE',

    'MEDIUM',

    c.component_name,

    'Production readiness concern: ' || ua.production_ready ||

    ' but working_status is ' || ua.working_status,

    'PROD_READINESS',

    datetime('now')

FROM   components c

JOIN   component_usage_analysis ua ON c.component_id = ua.component_id

WHERE  ua.is_active = 1

  AND  c.is_active  = 1

  AND  ua.production_ready = 'Yes'

  AND  ua.working_status  != 'Fully Working'



UNION ALL

/* 9.  Documentation gaps on critical work                  */

SELECT

    'DOCUMENTATION_ISSUE',

    'LOW',

    c.component_name,

    'Critical component lacks proper documentation (' || ua.documentation_status || ')',

    'DOC_MISSING',

    datetime('now')

FROM   components c

JOIN   component_usage_analysis ua ON c.component_id = ua.component_id

WHERE  ua.is_active = 1

  AND  c.is_active  = 1

  AND  ua.priority_to_fix IN ('HIGH','CRITICAL')

  AND  ua.documentation_status IN ('None','Limited','Basic')

  AND  ua.working_status = 'Fully Working'



UNION ALL

/* 10. **NEW**  Unresolved issues in component_issues       */

SELECT

    'OPEN_ISSUE',

    COALESCE(UPPER(ci.severity),'MEDIUM')           AS severity,

    c.component_name,

    'Unresolved issue: ' || ci.issue_description          AS description,

    'OPEN_COMPONENT_ISSUE'                          AS bug_category,

    COALESCE(ci.created_at, datetime('now'))        AS detected_at

FROM   "component_issues" ci

JOIN   components        c  ON ci.component_id = c.component_id

WHERE  ci.is_active = 1

  AND  ci.resolved   = 0

  AND  c.is_active   = 1
/* bug_detection_report(alert_type,severity,component_name,description,bug_category,detected_at) */;
