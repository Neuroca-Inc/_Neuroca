-- Phase 1: Create Normalized Table Structure with Constraints
-- Date: 2025-06-07
-- Purpose: Create normalized tables with PKs, FKs, indexes, and triggers (NO data migration)
-- WARNING: This only creates structure - does not touch existing data

-- =============================================================================
-- ENABLE FOREIGN KEY CONSTRAINTS
-- =============================================================================

PRAGMA foreign_keys = ON;

SELECT 'PHASE 1: Creating normalized table structure...' as status;

-- =============================================================================
-- CREATE MISSING LOOKUP TABLES
-- =============================================================================

SELECT 'Creating lookup tables...' as status;

-- Create missing working_statuses table
CREATE TABLE IF NOT EXISTS working_statuses (
    working_status_id INTEGER PRIMARY KEY,
    status_name TEXT NOT NULL UNIQUE,
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT NOT NULL DEFAULT 'system',
    version INTEGER NOT NULL DEFAULT 1
);

-- Create working_statuses_history table for temporal tracking
CREATE TABLE IF NOT EXISTS working_statuses_history (
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

-- Create usage_methods lookup table
CREATE TABLE IF NOT EXISTS usage_methods (
    usage_method_id INTEGER PRIMARY KEY,
    method_name TEXT NOT NULL UNIQUE,
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT NOT NULL DEFAULT 'system',
    version INTEGER NOT NULL DEFAULT 1
);

-- Create usage_methods_history table
CREATE TABLE IF NOT EXISTS usage_methods_history (
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

-- Create documentation_statuses lookup table
CREATE TABLE IF NOT EXISTS documentation_statuses (
    doc_status_id INTEGER PRIMARY KEY,
    status_name TEXT NOT NULL UNIQUE,
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT NOT NULL DEFAULT 'system',
    version INTEGER NOT NULL DEFAULT 1
);

-- Create documentation_statuses_history table
CREATE TABLE IF NOT EXISTS documentation_statuses_history (
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

-- Create testing_statuses lookup table  
CREATE TABLE IF NOT EXISTS testing_statuses (
    test_status_id INTEGER PRIMARY KEY,
    status_name TEXT NOT NULL UNIQUE,
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT NOT NULL DEFAULT 'system',
    version INTEGER NOT NULL DEFAULT 1
);

-- Create testing_statuses_history table
CREATE TABLE IF NOT EXISTS testing_statuses_history (
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
);

SELECT 'Lookup tables created' as status;

-- =============================================================================
-- CREATE NORMALIZED COMPONENT_USAGE_ANALYSIS TABLE
-- =============================================================================

SELECT 'Creating normalized component_usage_analysis_v2 table...' as status;

-- Create new normalized table with proper constraints
CREATE TABLE IF NOT EXISTS component_usage_analysis_v2 (
    analysis_id INTEGER PRIMARY KEY,
    component_id INTEGER NOT NULL,
    expected_usage TEXT NOT NULL DEFAULT 'Usage analysis pending',
    actual_integration_status TEXT NOT NULL DEFAULT 'Integration status needs assessment',
    missing_dependencies TEXT NOT NULL DEFAULT 'None identified',
    integration_issues TEXT NOT NULL DEFAULT 'None identified',
    working_status_id INTEGER NOT NULL DEFAULT 1,
    priority_id INTEGER NOT NULL DEFAULT 3,
    complexity_id INTEGER NOT NULL DEFAULT 2,
    usage_method_id INTEGER NOT NULL DEFAULT 1,
    doc_status_id INTEGER NOT NULL DEFAULT 1,
    test_status_id INTEGER NOT NULL DEFAULT 1,
    readiness_id INTEGER NOT NULL DEFAULT 4,
    current_file_paths TEXT NOT NULL DEFAULT 'N/A',
    entry_points TEXT NOT NULL DEFAULT 'No specific entry points',
    dependencies_on TEXT NOT NULL DEFAULT 'Standard dependencies only',
    dependencies_from TEXT NOT NULL DEFAULT 'No dependencies identified',
    performance_impact TEXT NOT NULL DEFAULT 'Not assessed',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT NOT NULL DEFAULT 'system',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    version INTEGER NOT NULL DEFAULT 1,
    
    -- Check constraints for data quality
    CHECK (length(expected_usage) > 0),
    CHECK (length(actual_integration_status) > 0),
    CHECK (version >= 1),
    CHECK (analysis_id > 0),
    CHECK (component_id > 0),
    
    -- Foreign Key Constraints
    FOREIGN KEY (component_id) REFERENCES components(component_id) ON DELETE CASCADE,
    FOREIGN KEY (working_status_id) REFERENCES working_statuses(working_status_id),
    FOREIGN KEY (priority_id) REFERENCES priority_levels(priority_id),
    FOREIGN KEY (complexity_id) REFERENCES complexity_levels(complexity_id),
    FOREIGN KEY (usage_method_id) REFERENCES usage_methods(usage_method_id),
    FOREIGN KEY (doc_status_id) REFERENCES documentation_statuses(doc_status_id),
    FOREIGN KEY (test_status_id) REFERENCES testing_statuses(test_status_id),
    FOREIGN KEY (readiness_id) REFERENCES readiness_statuses(readiness_id)
);

-- Create corresponding history table
CREATE TABLE IF NOT EXISTS component_usage_analysis_v2_history (
    history_id INTEGER PRIMARY KEY,
    analysis_id INTEGER NOT NULL,
    component_id INTEGER NOT NULL,
    expected_usage TEXT NOT NULL,
    actual_integration_status TEXT NOT NULL,
    missing_dependencies TEXT NOT NULL,
    integration_issues TEXT NOT NULL,
    working_status_id INTEGER NOT NULL,
    priority_id INTEGER NOT NULL,
    complexity_id INTEGER NOT NULL,
    usage_method_id INTEGER NOT NULL,
    doc_status_id INTEGER NOT NULL,
    test_status_id INTEGER NOT NULL,
    readiness_id INTEGER NOT NULL,
    current_file_paths TEXT NOT NULL,
    entry_points TEXT NOT NULL,
    dependencies_on TEXT NOT NULL,
    dependencies_from TEXT NOT NULL,
    performance_impact TEXT NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    created_by TEXT NOT NULL,
    is_active BOOLEAN NOT NULL,
    version INTEGER NOT NULL,
    history_operation TEXT NOT NULL CHECK (history_operation IN ('INSERT', 'UPDATE', 'DELETE')),
    history_timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    history_user TEXT NOT NULL DEFAULT 'system'
);

SELECT 'Normalized component_usage_analysis_v2 table created' as status;

-- =============================================================================
-- CREATE INDEXES FOR PERFORMANCE
-- =============================================================================

SELECT 'Creating indexes...' as status;

-- Primary table indexes
CREATE INDEX IF NOT EXISTS idx_component_usage_analysis_v2_component_id 
    ON component_usage_analysis_v2(component_id);
CREATE INDEX IF NOT EXISTS idx_component_usage_analysis_v2_working_status 
    ON component_usage_analysis_v2(working_status_id);
CREATE INDEX IF NOT EXISTS idx_component_usage_analysis_v2_priority 
    ON component_usage_analysis_v2(priority_id);
CREATE INDEX IF NOT EXISTS idx_component_usage_analysis_v2_complexity 
    ON component_usage_analysis_v2(complexity_id);
CREATE INDEX IF NOT EXISTS idx_component_usage_analysis_v2_updated_at 
    ON component_usage_analysis_v2(updated_at);
CREATE INDEX IF NOT EXISTS idx_component_usage_analysis_v2_active 
    ON component_usage_analysis_v2(is_active);

-- Composite indexes for common queries
CREATE INDEX IF NOT EXISTS idx_component_usage_analysis_v2_status_priority 
    ON component_usage_analysis_v2(working_status_id, priority_id);
CREATE INDEX IF NOT EXISTS idx_component_usage_analysis_v2_component_active 
    ON component_usage_analysis_v2(component_id, is_active);

-- History table indexes
CREATE INDEX IF NOT EXISTS idx_component_usage_analysis_v2_history_analysis_id 
    ON component_usage_analysis_v2_history(analysis_id);
CREATE INDEX IF NOT EXISTS idx_component_usage_analysis_v2_history_timestamp 
    ON component_usage_analysis_v2_history(history_timestamp);
CREATE INDEX IF NOT EXISTS idx_component_usage_analysis_v2_history_operation 
    ON component_usage_analysis_v2_history(history_operation);

-- Lookup table indexes
CREATE INDEX IF NOT EXISTS idx_working_statuses_active ON working_statuses(is_active);
CREATE INDEX IF NOT EXISTS idx_usage_methods_active ON usage_methods(is_active);
CREATE INDEX IF NOT EXISTS idx_documentation_statuses_active ON documentation_statuses(is_active);
CREATE INDEX IF NOT EXISTS idx_testing_statuses_active ON testing_statuses(is_active);

SELECT 'Indexes created' as status;

-- =============================================================================
-- CREATE TEMPORAL TRIGGERS FOR HISTORY TRACKING
-- =============================================================================

SELECT 'Creating temporal triggers...' as status;

-- working_statuses triggers
CREATE TRIGGER IF NOT EXISTS working_statuses_insert_history
AFTER INSERT ON working_statuses
FOR EACH ROW
BEGIN
    INSERT INTO working_statuses_history (
        working_status_id, status_name, description, is_active,
        created_at, updated_at, created_by, version,
        history_operation, history_user
    ) VALUES (
        NEW.working_status_id, NEW.status_name, NEW.description, NEW.is_active,
        NEW.created_at, NEW.updated_at, NEW.created_by, NEW.version,
        'INSERT', NEW.created_by
    );
END;

CREATE TRIGGER IF NOT EXISTS working_statuses_update_history
AFTER UPDATE ON working_statuses
FOR EACH ROW
BEGIN
    INSERT INTO working_statuses_history (
        working_status_id, status_name, description, is_active,
        created_at, updated_at, created_by, version,
        history_operation, history_user
    ) VALUES (
        NEW.working_status_id, NEW.status_name, NEW.description, NEW.is_active,
        NEW.created_at, NEW.updated_at, NEW.created_by, NEW.version,
        'UPDATE', NEW.created_by
    );
END;

-- usage_methods triggers
CREATE TRIGGER IF NOT EXISTS usage_methods_insert_history
AFTER INSERT ON usage_methods
FOR EACH ROW
BEGIN
    INSERT INTO usage_methods_history (
        usage_method_id, method_name, description, is_active,
        created_at, updated_at, created_by, version,
        history_operation, history_user
    ) VALUES (
        NEW.usage_method_id, NEW.method_name, NEW.description, NEW.is_active,
        NEW.created_at, NEW.updated_at, NEW.created_by, NEW.version,
        'INSERT', NEW.created_by
    );
END;

CREATE TRIGGER IF NOT EXISTS usage_methods_update_history
AFTER UPDATE ON usage_methods
FOR EACH ROW
BEGIN
    INSERT INTO usage_methods_history (
        usage_method_id, method_name, description, is_active,
        created_at, updated_at, created_by, version,
        history_operation, history_user
    ) VALUES (
        NEW.usage_method_id, NEW.method_name, NEW.description, NEW.is_active,
        NEW.created_at, NEW.updated_at, NEW.created_by, NEW.version,
        'UPDATE', NEW.created_by
    );
END;

-- documentation_statuses triggers
CREATE TRIGGER IF NOT EXISTS documentation_statuses_insert_history
AFTER INSERT ON documentation_statuses
FOR EACH ROW
BEGIN
    INSERT INTO documentation_statuses_history (
        doc_status_id, status_name, description, is_active,
        created_at, updated_at, created_by, version,
        history_operation, history_user
    ) VALUES (
        NEW.doc_status_id, NEW.status_name, NEW.description, NEW.is_active,
        NEW.created_at, NEW.updated_at, NEW.created_by, NEW.version,
        'INSERT', NEW.created_by
    );
END;

CREATE TRIGGER IF NOT EXISTS documentation_statuses_update_history
AFTER UPDATE ON documentation_statuses
FOR EACH ROW
BEGIN
    INSERT INTO documentation_statuses_history (
        doc_status_id, status_name, description, is_active,
        created_at, updated_at, created_by, version,
        history_operation, history_user
    ) VALUES (
        NEW.doc_status_id, NEW.status_name, NEW.description, NEW.is_active,
        NEW.created_at, NEW.updated_at, NEW.created_by, NEW.version,
        'UPDATE', NEW.created_by
    );
END;

-- testing_statuses triggers
CREATE TRIGGER IF NOT EXISTS testing_statuses_insert_history
AFTER INSERT ON testing_statuses
FOR EACH ROW
BEGIN
    INSERT INTO testing_statuses_history (
        test_status_id, status_name, description, is_active,
        created_at, updated_at, created_by, version,
        history_operation, history_user
    ) VALUES (
        NEW.test_status_id, NEW.status_name, NEW.description, NEW.is_active,
        NEW.created_at, NEW.updated_at, NEW.created_by, NEW.version,
        'INSERT', NEW.created_by
    );
END;

CREATE TRIGGER IF NOT EXISTS testing_statuses_update_history
AFTER UPDATE ON testing_statuses
FOR EACH ROW
BEGIN
    INSERT INTO testing_statuses_history (
        test_status_id, status_name, description, is_active,
        created_at, updated_at, created_by, version,
        history_operation, history_user
    ) VALUES (
        NEW.test_status_id, NEW.status_name, NEW.description, NEW.is_active,
        NEW.created_at, NEW.updated_at, NEW.created_by, NEW.version,
        'UPDATE', NEW.created_by
    );
END;

-- component_usage_analysis_v2 triggers
CREATE TRIGGER IF NOT EXISTS component_usage_analysis_v2_insert_history
AFTER INSERT ON component_usage_analysis_v2
FOR EACH ROW
BEGIN
    INSERT INTO component_usage_analysis_v2_history (
        analysis_id, component_id, expected_usage, actual_integration_status,
        missing_dependencies, integration_issues, working_status_id, priority_id,
        complexity_id, usage_method_id, doc_status_id, test_status_id, readiness_id,
        current_file_paths, entry_points, dependencies_on, dependencies_from,
        performance_impact, created_at, updated_at, created_by, is_active, version,
        history_operation, history_user
    ) VALUES (
        NEW.analysis_id, NEW.component_id, NEW.expected_usage, NEW.actual_integration_status,
        NEW.missing_dependencies, NEW.integration_issues, NEW.working_status_id, NEW.priority_id,
        NEW.complexity_id, NEW.usage_method_id, NEW.doc_status_id, NEW.test_status_id, NEW.readiness_id,
        NEW.current_file_paths, NEW.entry_points, NEW.dependencies_on, NEW.dependencies_from,
        NEW.performance_impact, NEW.created_at, NEW.updated_at, NEW.created_by, NEW.is_active, NEW.version,
        'INSERT', NEW.created_by
    );
END;

CREATE TRIGGER IF NOT EXISTS component_usage_analysis_v2_update_history
AFTER UPDATE ON component_usage_analysis_v2
FOR EACH ROW
BEGIN
    INSERT INTO component_usage_analysis_v2_history (
        analysis_id, component_id, expected_usage, actual_integration_status,
        missing_dependencies, integration_issues, working_status_id, priority_id,
        complexity_id, usage_method_id, doc_status_id, test_status_id, readiness_id,
        current_file_paths, entry_points, dependencies_on, dependencies_from,
        performance_impact, created_at, updated_at, created_by, is_active, version,
        history_operation, history_user
    ) VALUES (
        NEW.analysis_id, NEW.component_id, NEW.expected_usage, NEW.actual_integration_status,
        NEW.missing_dependencies, NEW.integration_issues, NEW.working_status_id, NEW.priority_id,
        NEW.complexity_id, NEW.usage_method_id, NEW.doc_status_id, NEW.test_status_id, NEW.readiness_id,
        NEW.current_file_paths, NEW.entry_points, NEW.dependencies_on, NEW.dependencies_from,
        NEW.performance_impact, NEW.created_at, NEW.updated_at, NEW.created_by, NEW.is_active, NEW.version,
        'UPDATE', NEW.created_by
    );
END;

-- Auto-update timestamp and version trigger
CREATE TRIGGER IF NOT EXISTS component_usage_analysis_v2_update_timestamp
BEFORE UPDATE ON component_usage_analysis_v2
FOR EACH ROW
BEGIN
    UPDATE component_usage_analysis_v2
    SET updated_at = CURRENT_TIMESTAMP,
        version = OLD.version + 1
    WHERE analysis_id = NEW.analysis_id;
END;

SELECT 'Temporal triggers created' as status;

-- =============================================================================
-- VALIDATION AND VERIFICATION
-- =============================================================================

SELECT 'PHASE 1 VALIDATION: Verifying table structure...' as status;

-- Check table existence
SELECT 'Tables created:' as validation;
SELECT name FROM sqlite_master WHERE type='table' AND name IN (
    'working_statuses', 'usage_methods', 'documentation_statuses', 
    'testing_statuses', 'component_usage_analysis_v2'
) ORDER BY name;

-- Check history tables
SELECT 'History tables created:' as validation;
SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%_history' 
AND name IN (
    'working_statuses_history', 'usage_methods_history', 
    'documentation_statuses_history', 'testing_statuses_history',
    'component_usage_analysis_v2_history'
) ORDER BY name;

-- Check indexes
SELECT 'Indexes created: ' || COUNT(*) as validation
FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%';

-- Check triggers
SELECT 'Triggers created: ' || COUNT(*) as validation
FROM sqlite_master WHERE type='trigger' AND name LIKE '%_history' OR name LIKE '%_timestamp';

-- Verify foreign key constraints are enabled
PRAGMA foreign_key_check;

SELECT 'PHASE 1 COMPLETE: Normalized table structure with constraints, indexes, and triggers created!' as status;
SELECT 'Ready for Phase 2: Data migration' as next_step;
