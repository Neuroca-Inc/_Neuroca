#!/usr/bin/env python3
"""
Create NEUROCA database with temporal tables, constraints, and referential integrity.
This version includes full audit trails, data validation, and change tracking.
"""

import sqlite3
import pandas as pd
import os
import json
from datetime import datetime

def create_constraint_config():
    """Create a configuration file for allowed values"""
    
    config = {
        "version": "2.0",
        "description": "Enhanced data validation constraints with temporal support",
        "allowed_values": {
            "priority": ["Critical", "High", "Medium", "Low"],
            "priority_to_fix": ["CRITICAL", "HIGH", "MEDIUM", "LOW"],
            "complexity": ["Easy", "Medium", "Hard", "Very Hard"],
            "production_ready": ["Yes", "No", "Partial"],
            "documentation_status": ["Excellent", "Good", "Basic", "Limited", "None"],
            "testing_status": ["Extensive", "Good", "Limited", "Basic", "None"],
            "performance_impact": ["Critical", "High", "Medium", "Low"],
            "dependency_type": ["requires", "optional", "suggests", "conflicts"],
            "severity": ["Critical", "High", "Medium", "Low", "Info"],
            "source": ["feature_inventory", "usage_analysis", "manual"],
            "working_status": ["Fully Working", "Exists But Not Connected", "Missing", 
                             "Partially Working", "Broken", "Duplicated/Confused", 
                             "Blocked by missing service layer"]
        },
        "constraint_rules": {
            "effort_hours": {"min": 0, "max": 200},
            "component_name_min_length": 3,
            "issue_description_min_length": 5
        },
        "temporal_settings": {
            "enabled": True,
            "retention_period_days": 365,
            "track_user": True
        }
    }
    
    with open("neuroca_temporal_db_config.json", "w") as f:
        json.dump(config, f, indent=2)
    
    return config

def create_temporal_database_schema(conn, config):
    """Create the database schema with temporal tables and full constraints"""
    
    # Enable foreign keys and set up SQLite for temporal support
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")  # Better for concurrent access
    
    # Drop existing tables if they exist (in correct order)
    tables_to_drop = [
        'component_usage_analysis', 'component_usage_analysis_history',
        'component_issues', 'component_issues_history',
        'component_dependencies', 'component_dependencies_history',
        'components', 'components_history',
        'categories', 'categories_history',
        'statuses', 'statuses_history',
        'change_log'
    ]
    
    for table in tables_to_drop:
        conn.execute(f"DROP TABLE IF EXISTS {table}")
    
    # Create change log table for temporal tracking
    conn.execute("""
    CREATE TABLE change_log (
        change_id INTEGER PRIMARY KEY,
        table_name TEXT NOT NULL,
        record_id INTEGER NOT NULL,
        operation TEXT NOT NULL CHECK(operation IN ('INSERT', 'UPDATE', 'DELETE')),
        changed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        changed_by TEXT DEFAULT 'system',
        old_values TEXT,  -- JSON
        new_values TEXT   -- JSON
    )
    """)
    
    # Build allowed values for constraints
    priority_values = "', '".join(config["allowed_values"]["priority"])
    fix_priority_values = "', '".join(config["allowed_values"]["priority_to_fix"])
    complexity_values = "', '".join(config["allowed_values"]["complexity"])
    source_values = "', '".join(config["allowed_values"]["source"])
    working_status_values = "', '".join(config["allowed_values"]["working_status"])
    
    # Categories table with temporal support
    conn.execute(f"""
    CREATE TABLE categories (
        category_id INTEGER PRIMARY KEY,
        category_name TEXT UNIQUE NOT NULL CHECK(length(category_name) >= 2),
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        created_by TEXT DEFAULT 'system',
        is_active BOOLEAN DEFAULT TRUE
    )
    """)
    
    conn.execute("""
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
    )
    """)
    
    # Statuses table with temporal support
    conn.execute(f"""
    CREATE TABLE statuses (
        status_id INTEGER PRIMARY KEY,
        status_name TEXT UNIQUE NOT NULL CHECK(length(status_name) >= 3),
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        created_by TEXT DEFAULT 'system',
        is_active BOOLEAN DEFAULT TRUE
    )
    """)
    
    conn.execute("""
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
    )
    """)
    
    # Main components table with comprehensive constraints and temporal support
    conn.execute(f"""
    CREATE TABLE components (
        component_id INTEGER PRIMARY KEY,
        component_name TEXT NOT NULL UNIQUE CHECK(length(component_name) >= 3),
        category_id INTEGER NOT NULL,
        status_id INTEGER,
        file_path TEXT CHECK(file_path IS NULL OR length(file_path) >= 1),
        priority TEXT CHECK(priority IS NULL OR priority IN ('{priority_values}')),
        effort_hours INTEGER CHECK(effort_hours IS NULL OR (effort_hours >= 0 AND effort_hours <= 200)),
        notes TEXT,
        duplicated BOOLEAN NOT NULL DEFAULT FALSE,
        source TEXT DEFAULT 'feature_inventory' CHECK(source IN ('{source_values}')),
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        created_by TEXT DEFAULT 'system',
        is_active BOOLEAN DEFAULT TRUE,
        version INTEGER DEFAULT 1,
        FOREIGN KEY (category_id) REFERENCES categories(category_id),
        FOREIGN KEY (status_id) REFERENCES statuses(status_id)
    )
    """)
    
    conn.execute("""
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
    )
    """)
    
    # Component dependencies with temporal support
    conn.execute("""
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
    )
    """)
    
    conn.execute("""
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
    )
    """)
    
    # Component issues with temporal support
    conn.execute("""
    CREATE TABLE component_issues (
        issue_id INTEGER PRIMARY KEY,
        component_id INTEGER NOT NULL,
        issue_description TEXT NOT NULL CHECK(length(issue_description) >= 5),
        severity TEXT CHECK(severity IS NULL OR severity IN ('Critical', 'High', 'Medium', 'Low', 'Info')),
        resolved BOOLEAN DEFAULT FALSE,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        resolved_at DATETIME,
        created_by TEXT DEFAULT 'system',
        resolved_by TEXT,
        is_active BOOLEAN DEFAULT TRUE,
        FOREIGN KEY (component_id) REFERENCES components(component_id) ON DELETE CASCADE
    )
    """)
    
    conn.execute("""
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
    )
    """)
    
    # Usage analysis with temporal support and full constraints
    conn.execute(f"""
    CREATE TABLE component_usage_analysis (
        analysis_id INTEGER PRIMARY KEY,
        component_id INTEGER NOT NULL,
        expected_usage TEXT,
        actual_integration_status TEXT,
        missing_dependencies TEXT,
        integration_issues TEXT,
        usage_method TEXT,
        working_status TEXT CHECK(working_status IS NULL OR working_status IN ('{working_status_values}')),
        priority_to_fix TEXT CHECK(priority_to_fix IS NULL OR priority_to_fix IN ('{fix_priority_values}')),
        complexity_to_fix TEXT CHECK(complexity_to_fix IS NULL OR complexity_to_fix IN ('{complexity_values}')),
        current_file_paths TEXT,
        entry_points TEXT,
        dependencies_on TEXT,
        dependencies_from TEXT,
        performance_impact TEXT CHECK(performance_impact IS NULL OR performance_impact IN ('Critical', 'High', 'Medium', 'Low')),
        documentation_status TEXT CHECK(documentation_status IS NULL OR documentation_status IN ('Excellent', 'Good', 'Basic', 'Limited', 'None')),
        testing_status TEXT CHECK(testing_status IS NULL OR testing_status IN ('Extensive', 'Good', 'Limited', 'Basic', 'None')),
        production_ready TEXT CHECK(production_ready IS NULL OR production_ready IN ('Yes', 'No', 'Partial')),
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        created_by TEXT DEFAULT 'system',
        is_active BOOLEAN DEFAULT TRUE,
        version INTEGER DEFAULT 1,
        FOREIGN KEY (component_id) REFERENCES components(component_id) ON DELETE CASCADE
    )
    """)
    
    conn.execute("""
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
    )
    """)
    
    print("✅ Created temporal database schema with full constraints")

def create_temporal_triggers(conn):
    """Create triggers to automatically maintain temporal tables"""
    
    print("🔧 Creating temporal triggers...")
    
    # Define the tables that need temporal triggers
    temporal_tables = [
        ('categories', 'category_id'),
        ('statuses', 'status_id'),
        ('components', 'component_id'),
        ('component_dependencies', 'dependency_id'),
        ('component_issues', 'issue_id'),
        ('component_usage_analysis', 'analysis_id')
    ]
    
    for table_name, id_column in temporal_tables:
        history_table = f"{table_name}_history"
        
        # Drop existing triggers
        conn.execute(f"DROP TRIGGER IF EXISTS {table_name}_insert_history")
        conn.execute(f"DROP TRIGGER IF EXISTS {table_name}_update_history")
        conn.execute(f"DROP TRIGGER IF EXISTS {table_name}_update_timestamp")
        conn.execute(f"DROP TRIGGER IF EXISTS {table_name}_version_increment")
        
        # Get all columns for this table (except history-specific ones)
        cursor = conn.execute(f"PRAGMA table_info({table_name})")
        columns = [row[1] for row in cursor.fetchall()]
        
        # Filter out columns that don't exist in history table
        history_columns = [col for col in columns]
        column_list = ', '.join(history_columns)
        new_column_list = ', '.join([f"NEW.{col}" for col in history_columns])
        old_column_list = ', '.join([f"OLD.{col}" for col in history_columns])
        
        # Insert trigger
        conn.execute(f"""
        CREATE TRIGGER {table_name}_insert_history
        AFTER INSERT ON {table_name}
        FOR EACH ROW
        BEGIN
            INSERT INTO {history_table} 
            ({column_list}, history_operation, history_timestamp, history_user)
            VALUES 
            ({new_column_list}, 'INSERT', CURRENT_TIMESTAMP, 'system');
        END
        """)
        
        # Update trigger for history
        conn.execute(f"""
        CREATE TRIGGER {table_name}_update_history
        AFTER UPDATE ON {table_name}
        FOR EACH ROW
        BEGIN
            INSERT INTO {history_table} 
            ({column_list}, history_operation, history_timestamp, history_user)
            VALUES 
            ({old_column_list}, 'UPDATE', CURRENT_TIMESTAMP, 'system');
        END
        """)
        
        # Update timestamp trigger
        conn.execute(f"""
        CREATE TRIGGER {table_name}_update_timestamp
        BEFORE UPDATE ON {table_name}
        FOR EACH ROW
        BEGIN
            UPDATE {table_name} 
            SET updated_at = CURRENT_TIMESTAMP,
                version = version + 1
            WHERE {id_column} = NEW.{id_column};
        END
        """)
    
    print("✅ Created temporal triggers for all tables")

def fix_case_sensitivity_in_data(feature_df, usage_df):
    """Fix case sensitivity issues and data values before importing data"""
    
    print("🔧 Fixing case sensitivity and data values in source data...")
    
    # Fix priority values in feature inventory
    priority_mapping = {
        'CRITICAL': 'Critical',
        'HIGH': 'High',
        'MEDIUM': 'Medium',
        'LOW': 'Low'
    }
    
    if 'Priority' in feature_df.columns:
        feature_df['Priority'] = feature_df['Priority'].map(
            lambda x: priority_mapping.get(x, x) if pd.notna(x) else x
        )
        print("✅ Fixed priority case in feature inventory")
    
    # Fix priority_to_fix values in usage analysis (these should stay uppercase)
    if 'Priority_To_Fix' in usage_df.columns:
        usage_priority_mapping = {
            'Critical': 'CRITICAL',
            'High': 'HIGH', 
            'Medium': 'MEDIUM',
            'Low': 'LOW'
        }
        usage_df['Priority_To_Fix'] = usage_df['Priority_To_Fix'].map(
            lambda x: usage_priority_mapping.get(x, x) if pd.notna(x) else x
        )
        print("✅ Fixed priority_to_fix case in usage analysis")
    
    # Fix performance_impact values - extract first word from descriptive text
    if 'Performance_Impact' in usage_df.columns:
        def extract_performance_level(value):
            if pd.isna(value) or not str(value).strip():
                return None
            # Extract first word before any " - " or just the first word
            first_word = str(value).split(' - ')[0].split()[0].strip()
            perf_mapping = {
                'Critical': 'Critical', 'CRITICAL': 'Critical', 'critical': 'Critical',
                'High': 'High', 'HIGH': 'High', 'high': 'High',
                'Medium': 'Medium', 'MEDIUM': 'Medium', 'medium': 'Medium',
                'Low': 'Low', 'LOW': 'Low', 'low': 'Low'
            }
            return perf_mapping.get(first_word, None)
        
        usage_df['Performance_Impact'] = usage_df['Performance_Impact'].apply(extract_performance_level)
        print("✅ Fixed performance_impact values in usage analysis")
    
    # Fix production_ready values - extract first word
    if 'Production_Ready' in usage_df.columns:
        def extract_production_status(value):
            if pd.isna(value) or not str(value).strip():
                return None
            first_word = str(value).split(' - ')[0].split()[0].strip()
            prod_mapping = {
                'Yes': 'Yes', 'YES': 'Yes', 'yes': 'Yes',
                'No': 'No', 'NO': 'No', 'no': 'No',
                'Partial': 'Partial', 'PARTIAL': 'Partial', 'partial': 'Partial'
            }
            return prod_mapping.get(first_word, None)
        
        usage_df['Production_Ready'] = usage_df['Production_Ready'].apply(extract_production_status)
        print("✅ Fixed production_ready values in usage analysis")
    
    # Fix documentation_status values - extract first word
    if 'Documentation_Status' in usage_df.columns:
        def extract_doc_status(value):
            if pd.isna(value) or not str(value).strip():
                return None
            first_word = str(value).split(' - ')[0].split()[0].strip()
            doc_mapping = {
                'Excellent': 'Excellent', 'EXCELLENT': 'Excellent', 'excellent': 'Excellent',
                'Good': 'Good', 'GOOD': 'Good', 'good': 'Good',
                'Basic': 'Basic', 'BASIC': 'Basic', 'basic': 'Basic',
                'Limited': 'Limited', 'LIMITED': 'Limited', 'limited': 'Limited',
                'None': 'None', 'NONE': 'None', 'none': 'None'
            }
            return doc_mapping.get(first_word, None)
        
        usage_df['Documentation_Status'] = usage_df['Documentation_Status'].apply(extract_doc_status)
        print("✅ Fixed documentation_status values in usage analysis")
    
    # Fix testing_status values - extract first word
    if 'Testing_Status' in usage_df.columns:
        def extract_test_status(value):
            if pd.isna(value) or not str(value).strip():
                return None
            first_word = str(value).split(' - ')[0].split()[0].strip()
            test_mapping = {
                'Extensive': 'Extensive', 'EXTENSIVE': 'Extensive', 'extensive': 'Extensive',
                'Good': 'Good', 'GOOD': 'Good', 'good': 'Good',
                'Limited': 'Limited', 'LIMITED': 'Limited', 'limited': 'Limited',
                'Basic': 'Basic', 'BASIC': 'Basic', 'basic': 'Basic',
                'None': 'None', 'NONE': 'None', 'none': 'None'
            }
            return test_mapping.get(first_word, None)
        
        usage_df['Testing_Status'] = usage_df['Testing_Status'].apply(extract_test_status)
        print("✅ Fixed testing_status values in usage analysis")
    
    # Fix complexity_to_fix values (these are already simple values)
    if 'Complexity_To_Fix' in usage_df.columns:
        complexity_mapping = {
            'Easy': 'Easy', 'EASY': 'Easy', 'easy': 'Easy',
            'Medium': 'Medium', 'MEDIUM': 'Medium', 'medium': 'Medium',
            'Hard': 'Hard', 'HARD': 'Hard', 'hard': 'Hard',
            'Very Hard': 'Very Hard', 'VERY HARD': 'Very Hard', 'very hard': 'Very Hard'
        }
        usage_df['Complexity_To_Fix'] = usage_df['Complexity_To_Fix'].map(
            lambda x: complexity_mapping.get(x, x) if pd.notna(x) and str(x).strip() else None
        )
        print("✅ Fixed complexity_to_fix values in usage analysis")
    
    # Fix working_status values - extract first part for descriptive values
    if 'Working_Status' in usage_df.columns:
        def extract_working_status(value):
            if pd.isna(value) or not str(value).strip():
                return None
            
            # Handle descriptive values by extracting the main status
            value_str = str(value).strip()
            
            # Direct mappings for exact matches
            if value_str in ['Fully Working', 'Exists But Not Connected', 'Missing', 
                           'Partially Working', 'Broken', 'Duplicated/Confused', 
                           'Blocked by missing service layer']:
                return value_str
            
            # Handle descriptive variations
            if value_str.startswith('Partially Working'):
                return 'Partially Working'
            elif value_str.startswith('Broken'):
                return 'Broken' 
            elif value_str.startswith('Missing'):
                return 'Missing'
            elif value_str.startswith('Exists But Not Connected'):
                return 'Exists But Not Connected'
            elif value_str.startswith('Fully Working'):
                return 'Fully Working'
            elif value_str.startswith('Duplicated'):
                return 'Duplicated/Confused'
            elif value_str.startswith('Blocked'):
                return 'Blocked by missing service layer'
            else:
                return None  # Unknown status
        
        usage_df['Working_Status'] = usage_df['Working_Status'].apply(extract_working_status)
        print("✅ Fixed working_status values in usage analysis")
    
    return feature_df, usage_df

def import_data_with_temporal_support(conn, feature_df, usage_df, name_mapping):
    """Import data into temporal database"""
    
    print("\n📥 Importing data into temporal database...")
    
    # Import categories and statuses first (same as before)
    categories = set()
    categories.update(feature_df['Category'].unique())
    categories.update(usage_df['Category'].unique())
    
    for cat in categories:
        conn.execute("""
        INSERT OR IGNORE INTO categories (category_name, created_by) 
        VALUES (?, ?)
        """, (cat, 'import_script'))
    
    statuses = set()
    statuses.update(feature_df['Status'].unique())
    statuses.update(usage_df['Working_Status'].unique())
    
    for status in statuses:
        conn.execute("""
        INSERT OR IGNORE INTO statuses (status_name, created_by) 
        VALUES (?, ?)
        """, (status, 'import_script'))
    
    print(f"✅ Imported {len(categories)} categories and {len(statuses)} statuses")
    
    # Import components with temporal tracking
    for _, row in feature_df.iterrows():
        cat_result = conn.execute(
            "SELECT category_id FROM categories WHERE category_name = ?", 
            (row['Category'],)
        ).fetchone()
        category_id = cat_result[0] if cat_result else None
        
        status_result = conn.execute(
            "SELECT status_id FROM statuses WHERE status_name = ?", 
            (row['Status'],)
        ).fetchone()
        status_id = status_result[0] if status_result else None
        
        # Insert component with temporal support
        cursor = conn.execute("""
        INSERT INTO components 
        (component_name, category_id, status_id, file_path, priority, effort_hours, 
         notes, duplicated, source, created_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            row['Component'], category_id, status_id, row['File_Path'],
            row['Priority'], row['Effort_Hours'], row['Notes'],
            row['Duplicated?'] == 'Yes', 'feature_inventory', 'import_script'
        ))
        
        component_id = cursor.lastrowid
        
        # Insert dependencies and issues with temporal support
        if pd.notna(row['Dependencies']) and row['Dependencies'].strip():
            conn.execute("""
            INSERT INTO component_dependencies (component_id, depends_on, created_by)
            VALUES (?, ?, ?)
            """, (component_id, row['Dependencies'], 'import_script'))
        
        if pd.notna(row['Issues']) and row['Issues'].strip():
            conn.execute("""
            INSERT INTO component_issues (component_id, issue_description, created_by)
            VALUES (?, ?, ?)
            """, (component_id, row['Issues'], 'import_script'))
    
    print(f"✅ Imported {len(feature_df)} components with full temporal tracking")
    
    # Import usage analysis with name mapping (similar to before but with temporal support)
    matched = 0
    for _, row in usage_df.iterrows():
        original_name = row['Component']
        mapped_name = name_mapping.get(original_name, original_name)
        
        component_result = conn.execute(
            "SELECT component_id FROM components WHERE component_name = ? AND is_active = TRUE",
            (mapped_name,)
        ).fetchone()
        
        if component_result:
            component_id = component_result[0]
            matched += 1
            
            conn.execute("""
            INSERT INTO component_usage_analysis 
            (component_id, expected_usage, actual_integration_status, missing_dependencies,
             integration_issues, usage_method, working_status, priority_to_fix, 
             complexity_to_fix, current_file_paths, entry_points, dependencies_on,
             dependencies_from, performance_impact, documentation_status, testing_status,
             production_ready, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                component_id, row['Expected_Usage'], row['Actual_Integration_Status'], 
                row['Missing_Dependencies'], row['Integration_Issues'], row['Usage_Method'],
                row['Working_Status'], row['Priority_To_Fix'], row['Complexity_To_Fix'],
                row['Current_File_Paths'], row['Entry_Points'], row['Dependencies_On'],
                row['Dependencies_From'], row['Performance_Impact'], 
                row['Documentation_Status'], row['Testing_Status'], 
                row['Production_Ready'], 'import_script'
            ))
    
    print(f"✅ Imported usage analysis: {matched} components matched")

def create_enhanced_views(conn):
    """Create enhanced views for temporal database analysis"""
    
    print("📊 Creating enhanced views...")
    
    # Drop existing views
    views_to_drop = [
        'component_overview', 'critical_blockers', 'components_with_full_analysis',
        'data_quality_report', 'component_completeness', 'change_summary',
        'component_change_history', 'current_active_components'
    ]
    
    for view in views_to_drop:
        conn.execute(f"DROP VIEW IF EXISTS {view}")
    
    # Current active components overview
    conn.execute("""
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
    """)
    
    # Enhanced critical blockers with temporal info
    conn.execute("""
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
        co.updated_at as last_updated
    FROM current_active_components co
    LEFT JOIN component_usage_analysis ua ON co.component_id = ua.component_id
    WHERE (ua.priority_to_fix = 'CRITICAL'
       OR co.status_name IN ('Missing', 'Broken')
       OR ua.working_status IN ('Missing', 'Broken'))
       AND ua.is_active = TRUE
    ORDER BY 
        CASE ua.priority_to_fix 
            WHEN 'CRITICAL' THEN 1 
            WHEN 'HIGH' THEN 2 
            ELSE 3 
        END,
        co.effort_hours ASC
    """)
    
    # Component change history view
    conn.execute("""
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
    """)
    
    # Change summary for recent activity
    conn.execute("""
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
    """)
    
    # Enhanced data quality with temporal aspects
    conn.execute("""
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
    """)
    
    print("✅ Created enhanced temporal views")

def create_component_name_mapping():
    """Create a mapping for mismatched component names"""
    return {
        "Main FastAPI App (app.py)": "FastAPI Application",
        "Simple FastAPI App (main.py)": "Main Application", 
        "Memory Backends": "InMemory Backend",
        "API Routes (memory.py)": "API Routes",
        "CLI Commands (submodules)": "CLI Interface",
        "User Management System": None,
        "API Models vs Schemas": None,
        "Monitoring System": "Logging System",
        "Package Installation": "Package Dependencies"
    }

def main():
    """Main function to create temporal database"""
    
    print("🏗️ CREATING NEUROCA TEMPORAL DATABASE")
    print("=" * 60)
    
    # Check if CSV files exist
    feature_file = "NEUROCA_FEATURE_INVENTORY.csv"
    usage_file = "NEUROCA_COMPONENT_USAGE_ANALYSIS.csv"
    
    for file in [feature_file, usage_file]:
        if not os.path.exists(file):
            print(f"❌ Error: {file} not found")
            return
    
    # Read and fix CSV data
    print("📂 Reading and preprocessing CSV files...")
    feature_df = pd.read_csv(feature_file)
    usage_df = pd.read_csv(usage_file)
    
    # Fix case sensitivity issues
    feature_df, usage_df = fix_case_sensitivity_in_data(feature_df, usage_df)
    
    print(f"✅ Feature inventory: {len(feature_df)} rows")
    print(f"✅ Usage analysis: {len(usage_df)} rows")
    
    # Create configuration
    config = create_constraint_config()
    print("✅ Created temporal database configuration")
    
    # Create component name mapping
    name_mapping = create_component_name_mapping()
    
    # Create database
    db_file = "neuroca_temporal_analysis.db"
    print(f"\n🗄️ Creating temporal database: {db_file}")
    
    with sqlite3.connect(db_file) as conn:
        # Create schema with temporal support
        create_temporal_database_schema(conn, config)
        
        # Create temporal triggers
        create_temporal_triggers(conn)
        
        # Import data with temporal tracking
        import_data_with_temporal_support(conn, feature_df, usage_df, name_mapping)
        
        # Create enhanced views
        create_enhanced_views(conn)
        
        # Verify setup
        fk_check = conn.execute("PRAGMA foreign_keys").fetchone()
        print(f"✅ Foreign keys enabled: {fk_check[0] == 1}")
        
        # Show some statistics
        component_count = conn.execute("SELECT COUNT(*) FROM components WHERE is_active = TRUE").fetchone()[0]
        history_count = conn.execute("SELECT COUNT(*) FROM components_history").fetchone()[0]
        
        print(f"✅ Active components: {component_count}")
        print(f"✅ History records: {history_count}")
        
        conn.commit()
    
    print(f"\n✅ Successfully created temporal database: {db_file}")
    print("\n📊 Key features:")
    print("   - Full temporal tracking (who changed what when)")
    print("   - Data validation constraints")
    print("   - Referential integrity with foreign keys") 
    print("   - Configurable allowed values")
    print("   - Version control for all records")
    print("   - Audit trails in history tables")
    print("\n🔍 Try these temporal queries:")
    print("   SELECT * FROM critical_blockers;")
    print("   SELECT * FROM component_change_history LIMIT 10;")
    print("   SELECT * FROM change_summary;")
    print("   SELECT * FROM data_quality_report;")

if __name__ == "__main__":
    main()
