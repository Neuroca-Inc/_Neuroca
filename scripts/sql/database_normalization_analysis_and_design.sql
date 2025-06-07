-- Database Normalization Analysis and Design
-- Date: 2025-06-07
-- Purpose: Analyze current denormalization issues and design proper 3NF schema

-- =============================================================================
-- CURRENT DENORMALIZATION ISSUES IDENTIFIED
-- =============================================================================

/*
ISSUE 1: Duplicate Audit Columns (Violates DRY)
- created_at, updated_at, created_by, is_active repeated in every table
- Should use inheritance or common audit pattern

ISSUE 2: Data Duplication in component_usage_analysis
- dependencies_on/dependencies_from duplicates component_dependencies table data
- integration_issues duplicates component_issues table data
- Multiple status fields could be normalized into lookup tables

ISSUE 3: Text-based References (Violates Referential Integrity)
- dependencies_on stores comma-separated text instead of FK references
- Status values hardcoded instead of lookup tables
- Missing proper foreign key relationships

ISSUE 4: Mixed Concerns (Violates Single Responsibility)
- component_usage_analysis contains too many different types of data:
  * Usage information
  * Status information  
  * Dependency information
  * Issue information
  * Documentation metadata
*/

-- =============================================================================
-- PROPOSED NORMALIZED SCHEMA DESIGN (3NF)
-- =============================================================================

-- Step 1: Create common audit pattern base
CREATE TABLE IF NOT EXISTS audit_log (
    audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
    table_name TEXT NOT NULL,
    record_id INTEGER NOT NULL,
    operation TEXT NOT NULL CHECK(operation IN ('INSERT', 'UPDATE', 'DELETE')),
    old_values TEXT, -- JSON format
    new_values TEXT, -- JSON format
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT DEFAULT 'system'
);

-- Step 2: Status lookup tables (normalize enum values)
CREATE TABLE IF NOT EXISTS working_statuses (
    status_id INTEGER PRIMARY KEY AUTOINCREMENT,
    status_name TEXT UNIQUE NOT NULL,
    status_description TEXT,
    is_active BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS priority_levels (
    priority_id INTEGER PRIMARY KEY AUTOINCREMENT,
    priority_name TEXT UNIQUE NOT NULL,
    priority_order INTEGER NOT NULL, -- 1=highest, 4=lowest
    is_active BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS complexity_levels (
    complexity_id INTEGER PRIMARY KEY AUTOINCREMENT,
    complexity_name TEXT UNIQUE NOT NULL,
    estimated_hours INTEGER, -- typical time estimate
    is_active BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS readiness_statuses (
    readiness_id INTEGER PRIMARY KEY AUTOINCREMENT,
    readiness_name TEXT UNIQUE NOT NULL,
    readiness_description TEXT,
    is_active BOOLEAN DEFAULT TRUE
);

-- Step 3: Normalized component core data (clean up main component_usage_analysis)
CREATE TABLE IF NOT EXISTS component_usage_core (
    usage_id INTEGER PRIMARY KEY AUTOINCREMENT,
    component_id INTEGER NOT NULL,
    expected_usage TEXT NOT NULL CHECK(length(expected_usage) > 10),
    actual_integration_status TEXT NOT NULL CHECK(length(actual_integration_status) > 5),
    usage_method TEXT NOT NULL CHECK(length(usage_method) > 5),
    current_file_paths TEXT NOT NULL CHECK(length(current_file_paths) > 3),
    entry_points TEXT DEFAULT 'No specific entry points',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT DEFAULT 'system',
    version INTEGER DEFAULT 1,
    FOREIGN KEY (component_id) REFERENCES components(component_id) ON DELETE CASCADE
);

-- Step 4: Component status tracking (normalized from mixed fields)
CREATE TABLE IF NOT EXISTS component_status (
    status_record_id INTEGER PRIMARY KEY AUTOINCREMENT,
    component_id INTEGER NOT NULL,
    working_status_id INTEGER NOT NULL,
    priority_id INTEGER NOT NULL,
    complexity_id INTEGER NOT NULL,
    readiness_id INTEGER NOT NULL,
    performance_impact TEXT CHECK(performance_impact IS NULL OR performance_impact IN ('Critical', 'High', 'Medium', 'Low')),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT DEFAULT 'system',
    version INTEGER DEFAULT 1,
    FOREIGN KEY (component_id) REFERENCES components(component_id) ON DELETE CASCADE,
    FOREIGN KEY (working_status_id) REFERENCES working_statuses(status_id),
    FOREIGN KEY (priority_id) REFERENCES priority_levels(priority_id),
    FOREIGN KEY (complexity_id) REFERENCES complexity_levels(complexity_id),
    FOREIGN KEY (readiness_id) REFERENCES readiness_statuses(readiness_id)
);

-- Step 5: Component metadata (documentation, testing status)
CREATE TABLE IF NOT EXISTS component_metadata (
    metadata_id INTEGER PRIMARY KEY AUTOINCREMENT,
    component_id INTEGER NOT NULL,
    metadata_type TEXT NOT NULL CHECK(metadata_type IN ('documentation', 'testing', 'deployment', 'maintenance')),
    metadata_value TEXT NOT NULL,
    metadata_details TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT DEFAULT 'system',
    version INTEGER DEFAULT 1,
    FOREIGN KEY (component_id) REFERENCES components(component_id) ON DELETE CASCADE,
    UNIQUE(component_id, metadata_type) -- One record per type per component
);

-- Step 6: Improved dependency relationships (fix text-based references)
-- Note: component_dependencies already exists, but improve with proper FK references
CREATE TABLE IF NOT EXISTS component_dependency_relationships (
    relationship_id INTEGER PRIMARY KEY AUTOINCREMENT,
    dependent_component_id INTEGER NOT NULL, -- Component that depends
    dependency_component_id INTEGER, -- Component being depended on (NULL for external deps)
    external_dependency_name TEXT, -- For external dependencies (libraries, etc.)
    dependency_type TEXT DEFAULT 'requires' CHECK(dependency_type IN ('requires', 'optional', 'suggests', 'conflicts')),
    version_constraint TEXT, -- e.g., ">=1.0.0", "^2.1.0"
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT DEFAULT 'system',
    is_active BOOLEAN DEFAULT TRUE,
    FOREIGN KEY (dependent_component_id) REFERENCES components(component_id) ON DELETE CASCADE,
    FOREIGN KEY (dependency_component_id) REFERENCES components(component_id) ON DELETE CASCADE,
    CHECK ((dependency_component_id IS NOT NULL AND external_dependency_name IS NULL) 
           OR (dependency_component_id IS NULL AND external_dependency_name IS NOT NULL))
);

-- =============================================================================
-- LOOKUP TABLE DATA POPULATION
-- =============================================================================

-- Populate working statuses
INSERT OR IGNORE INTO working_statuses (status_name, status_description) VALUES
    ('Working', 'Component is fully functional'),
    ('Broken', 'Component has critical issues preventing operation'),
    ('Partial', 'Component works but has limitations or issues'),
    ('Unknown', 'Working status has not been verified'),
    ('Not Tested', 'Component has not been tested yet');

-- Populate priority levels
INSERT OR IGNORE INTO priority_levels (priority_name, priority_order) VALUES
    ('CRITICAL', 1),
    ('HIGH', 2),
    ('MEDIUM', 3),
    ('LOW', 4);

-- Populate complexity levels
INSERT OR IGNORE INTO complexity_levels (complexity_name, estimated_hours) VALUES
    ('Easy', 2),
    ('Medium', 8),
    ('Hard', 20),
    ('Very Hard', 40);

-- Populate readiness statuses
INSERT OR IGNORE INTO readiness_statuses (readiness_name, readiness_description) VALUES
    ('Yes', 'Ready for production use'),
    ('No', 'Not ready for production'),
    ('Partial', 'Some features ready, others in development'),
    ('Unknown', 'Production readiness not assessed');

-- =============================================================================
-- DATA MIGRATION PLAN (from denormalized to normalized)
-- =============================================================================

-- Step 1: Migrate core usage data
INSERT OR REPLACE INTO component_usage_core (
    component_id, expected_usage, actual_integration_status, usage_method, 
    current_file_paths, entry_points, created_at, updated_at, created_by, version
)
SELECT 
    component_id, expected_usage, actual_integration_status, usage_method,
    current_file_paths, entry_points, created_at, updated_at, created_by, version
FROM component_usage_analysis;

-- Step 2: Migrate status data to normalized structure
INSERT OR REPLACE INTO component_status (
    component_id, working_status_id, priority_id, complexity_id, readiness_id,
    performance_impact, created_at, updated_at, created_by, version
)
SELECT 
    cua.component_id,
    ws.status_id,
    pl.priority_id,
    cl.complexity_id,
    rs.readiness_id,
    cua.performance_impact,
    cua.created_at,
    cua.updated_at,
    cua.created_by,
    cua.version
FROM component_usage_analysis cua
JOIN working_statuses ws ON ws.status_name = cua.working_status
JOIN priority_levels pl ON pl.priority_name = cua.priority_to_fix
JOIN complexity_levels cl ON cl.complexity_name = cua.complexity_to_fix
JOIN readiness_statuses rs ON rs.readiness_name = cua.production_ready;

-- Step 3: Migrate metadata (documentation, testing status)
INSERT OR REPLACE INTO component_metadata (component_id, metadata_type, metadata_value, created_at, updated_at, created_by, version)
SELECT component_id, 'documentation', documentation_status, created_at, updated_at, created_by, version
FROM component_usage_analysis
WHERE documentation_status IS NOT NULL;

INSERT OR REPLACE INTO component_metadata (component_id, metadata_type, metadata_value, created_at, updated_at, created_by, version)
SELECT component_id, 'testing', testing_status, created_at, updated_at, created_by, version
FROM component_usage_analysis
WHERE testing_status IS NOT NULL;

-- =============================================================================
-- VIEWS FOR BACKWARD COMPATIBILITY
-- =============================================================================

-- Create a view that mimics the old denormalized structure for existing queries
CREATE VIEW component_usage_analysis_view AS
SELECT 
    cuc.usage_id as analysis_id,
    cuc.component_id,
    cuc.expected_usage,
    cuc.actual_integration_status,
    cuc.usage_method,
    cuc.current_file_paths,
    cuc.entry_points,
    ws.status_name as working_status,
    pl.priority_name as priority_to_fix,
    cl.complexity_name as complexity_to_fix,
    rs.readiness_name as production_ready,
    cs.performance_impact,
    doc_meta.metadata_value as documentation_status,
    test_meta.metadata_value as testing_status,
    cuc.created_at,
    cuc.updated_at,
    cuc.created_by,
    cuc.version
FROM component_usage_core cuc
LEFT JOIN component_status cs ON cuc.component_id = cs.component_id
LEFT JOIN working_statuses ws ON cs.working_status_id = ws.status_id
LEFT JOIN priority_levels pl ON cs.priority_id = pl.priority_id
LEFT JOIN complexity_levels cl ON cs.complexity_id = cl.complexity_id
LEFT JOIN readiness_statuses rs ON cs.readiness_id = rs.readiness_id
LEFT JOIN component_metadata doc_meta ON cuc.component_id = doc_meta.component_id AND doc_meta.metadata_type = 'documentation'
LEFT JOIN component_metadata test_meta ON cuc.component_id = test_meta.component_id AND test_meta.metadata_type = 'testing';

-- =============================================================================
-- VERIFICATION QUERIES
-- =============================================================================

SELECT 'Normalization Design Complete!' as status;
SELECT 'Lookup Tables Created:' as info;
SELECT COUNT(*) as working_statuses_count FROM working_statuses;
SELECT COUNT(*) as priority_levels_count FROM priority_levels;
SELECT COUNT(*) as complexity_levels_count FROM complexity_levels;
SELECT COUNT(*) as readiness_statuses_count FROM readiness_statuses;
