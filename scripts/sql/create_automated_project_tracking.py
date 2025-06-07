#!/usr/bin/env python3
"""
Create Automated Project Tracking System
Extends neuroca_temporal_analysis.db with real-time file monitoring and drift detection
All monitoring scripts are stored IN the database for complete portability
"""

import sqlite3
from datetime import datetime
import os

def create_automated_tracking_system():
    """Create automated project tracking tables and store monitoring scripts in database."""
    
    print("🚀 CREATING AUTOMATED PROJECT TRACKING SYSTEM")
    print("=" * 65)
    
    # Connect to existing database
    conn = sqlite3.connect("neuroca_temporal_analysis.db")
    conn.execute("PRAGMA foreign_keys = ON")
    
    # ============ AUTOMATED DATA COLLECTION TABLES ============
    
    tables = [
        
        # Store automation scripts IN the database for portability
        """
        CREATE TABLE IF NOT EXISTS automation_scripts (
            script_id INTEGER PRIMARY KEY,
            script_name TEXT NOT NULL UNIQUE,
            script_description TEXT,
            script_code TEXT NOT NULL,
            script_type TEXT CHECK(script_type IN ('File Watcher', 'Data Collector', 'Analysis', 'Maintenance')),
            is_active BOOLEAN DEFAULT TRUE,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """,
        
        # Raw activity log (INSERT only, historical record)
        """
        CREATE TABLE IF NOT EXISTS file_activity_log (
            activity_id INTEGER PRIMARY KEY,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            file_path TEXT NOT NULL,
            file_name TEXT,
            file_extension TEXT,
            change_type TEXT CHECK(change_type IN ('created', 'modified', 'deleted', 'moved')),
            file_size_bytes INTEGER,
            lines_of_code INTEGER,
            component_id INTEGER,
            is_test_file BOOLEAN DEFAULT FALSE,
            is_documentation_file BOOLEAN DEFAULT FALSE,
            git_commit_hash TEXT,
            FOREIGN KEY (component_id) REFERENCES components(component_id)
        )
        """,
        
        # Current state of all files (INSERT + UPDATE)
        """
        CREATE TABLE IF NOT EXISTS current_file_status (
            file_id INTEGER PRIMARY KEY,
            file_path TEXT NOT NULL UNIQUE,
            file_name TEXT,
            file_extension TEXT,
            component_id INTEGER,
            current_size_bytes INTEGER,
            current_lines_of_code INTEGER,
            is_test_file BOOLEAN DEFAULT FALSE,
            is_documentation_file BOOLEAN DEFAULT FALSE,
            last_modified DATETIME,
            last_analyzed DATETIME DEFAULT CURRENT_TIMESTAMP,
            test_coverage_percentage REAL DEFAULT 0,
            complexity_score INTEGER DEFAULT 0,
            import_count INTEGER DEFAULT 0,
            function_count INTEGER DEFAULT 0,
            class_count INTEGER DEFAULT 0,
            FOREIGN KEY (component_id) REFERENCES components(component_id)
        )
        """,
        
        # Git activity tracking
        """
        CREATE TABLE IF NOT EXISTS git_activity_log (
            git_id INTEGER PRIMARY KEY,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            commit_hash TEXT,
            commit_message TEXT,
            author_name TEXT,
            files_changed INTEGER,
            lines_added INTEGER,
            lines_deleted INTEGER,
            files_affected TEXT -- JSON array of file paths
        )
        """,
        
        # Current project metrics snapshot
        """
        CREATE TABLE IF NOT EXISTS current_project_metrics (
            metric_id INTEGER PRIMARY KEY,
            metric_name TEXT NOT NULL UNIQUE,
            metric_value REAL NOT NULL,
            metric_unit TEXT,
            measurement_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            baseline_value REAL,
            threshold_warning REAL,
            threshold_critical REAL,
            trend_direction TEXT CHECK(trend_direction IN ('improving', 'stable', 'declining')),
            is_critical BOOLEAN DEFAULT FALSE
        )
        """,
        
        # Dependency tracking
        """
        CREATE TABLE IF NOT EXISTS dependency_tracking (
            dep_id INTEGER PRIMARY KEY,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            file_path TEXT NOT NULL,
            dependency_name TEXT NOT NULL,
            dependency_type TEXT CHECK(dependency_type IN ('import', 'require', 'include', 'pip', 'npm')),
            version TEXT,
            is_new_dependency BOOLEAN DEFAULT FALSE,
            is_security_critical BOOLEAN DEFAULT FALSE,
            component_id INTEGER,
            FOREIGN KEY (component_id) REFERENCES components(component_id)
        )
        """,
        
        # Active drift alerts (auto-resolving)
        """
        CREATE TABLE IF NOT EXISTS current_drift_alerts (
            alert_id INTEGER PRIMARY KEY,
            alert_type TEXT NOT NULL,
            severity TEXT CHECK(severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
            component_id INTEGER,
            file_path TEXT,
            alert_title TEXT NOT NULL,
            alert_description TEXT,
            detected_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            resolved_at DATETIME,
            is_active BOOLEAN DEFAULT TRUE,
            auto_generated BOOLEAN DEFAULT TRUE,
            threshold_value REAL,
            current_value REAL,
            FOREIGN KEY (component_id) REFERENCES components(component_id)
        )
        """,
        
        # Documentation sync tracking
        """
        CREATE TABLE IF NOT EXISTS documentation_sync_status (
            sync_id INTEGER PRIMARY KEY,
            component_id INTEGER NOT NULL,
            code_file_path TEXT,
            doc_file_path TEXT,
            code_last_modified DATETIME,
            doc_last_modified DATETIME,
            sync_gap_hours REAL,
            is_out_of_sync BOOLEAN DEFAULT FALSE,
            sync_score REAL DEFAULT 100, -- 0-100 scoring
            FOREIGN KEY (component_id) REFERENCES components(component_id)
        )
        """
    ]
    
    # Create all tables
    for i, table_sql in enumerate(tables, 1):
        try:
            conn.execute(table_sql)
            table_name = table_sql.split("CREATE TABLE IF NOT EXISTS ")[1].split(" (")[0]
            print(f"   ✅ {i:2d}. Created table: {table_name}")
        except Exception as e:
            print(f"   ❌ {i:2d}. Failed to create table: {e}")
    
    # ============ ANALYTICAL VIEWS FOR INSTANT HEALTH ASSESSMENT ============
    
    views = [
        
        # Real-time project health dashboard
        """
        CREATE VIEW IF NOT EXISTS realtime_project_health AS
        SELECT 
            'Project Health' as metric_category,
            COUNT(DISTINCT cfs.component_id) as total_active_components,
            COUNT(DISTINCT CASE WHEN cfs.last_modified > datetime('now', '-7 days') THEN cfs.component_id END) as components_active_this_week,
            AVG(cfs.test_coverage_percentage) as avg_test_coverage,
            COUNT(CASE WHEN cda.is_active = TRUE AND cda.severity IN ('HIGH', 'CRITICAL') THEN 1 END) as critical_issues,
            COUNT(CASE WHEN dss.is_out_of_sync = TRUE THEN 1 END) as documentation_sync_issues,
            ROUND(
                (COUNT(DISTINCT CASE WHEN cfs.last_modified > datetime('now', '-7 days') THEN cfs.component_id END) * 100.0) / 
                NULLIF(COUNT(DISTINCT cfs.component_id), 0), 1
            ) as activity_percentage,
            datetime('now') as last_updated
        FROM current_file_status cfs
        LEFT JOIN current_drift_alerts cda ON cfs.component_id = cda.component_id
        LEFT JOIN documentation_sync_status dss ON cfs.component_id = dss.component_id
        """,
        
        # Scope drift detection dashboard  
        """
        CREATE VIEW IF NOT EXISTS scope_drift_dashboard AS
        SELECT 
            c.component_name,
            c.category_name,
            COUNT(DISTINCT cfs.file_path) as current_file_count,
            SUM(cfs.current_lines_of_code) as current_total_loc,
            COUNT(DISTINCT dt.dependency_name) as current_dependencies,
            AVG(cfs.complexity_score) as avg_complexity,
            AVG(cfs.test_coverage_percentage) as test_coverage,
            COUNT(CASE WHEN fal.timestamp > datetime('now', '-7 days') THEN 1 END) as changes_this_week,
            COUNT(CASE WHEN dt.is_new_dependency = TRUE AND dt.timestamp > datetime('now', '-7 days') THEN 1 END) as new_deps_this_week,
            CASE 
                WHEN COUNT(CASE WHEN fal.timestamp > datetime('now', '-7 days') THEN 1 END) > 10 
                     AND AVG(cfs.test_coverage_percentage) < 70 THEN 'HIGH_ACTIVITY_LOW_TESTS'
                WHEN COUNT(DISTINCT dt.dependency_name) > 20 THEN 'DEPENDENCY_BLOAT'
                WHEN AVG(cfs.complexity_score) > 15 THEN 'COMPLEXITY_DRIFT'
                WHEN COUNT(CASE WHEN dt.is_new_dependency = TRUE AND dt.timestamp > datetime('now', '-7 days') THEN 1 END) > 3 THEN 'RAPID_DEPENDENCY_GROWTH'
                ELSE 'HEALTHY'
            END as drift_status,
            datetime('now') as analysis_timestamp
        FROM components c
        LEFT JOIN current_file_status cfs ON c.component_id = cfs.component_id
        LEFT JOIN file_activity_log fal ON c.component_id = fal.component_id
        LEFT JOIN dependency_tracking dt ON c.component_id = dt.component_id
        WHERE c.is_active = TRUE
        GROUP BY c.component_id, c.component_name, c.category_name
        """,
        
        # Progress velocity analysis
        """
        CREATE VIEW IF NOT EXISTS progress_velocity_analysis AS
        SELECT 
            'Last 7 Days' as period,
            COUNT(DISTINCT fal.file_path) as files_modified,
            COUNT(DISTINCT fal.component_id) as components_touched,
            SUM(CASE WHEN fal.change_type = 'created' THEN 1 ELSE 0 END) as files_created,
            SUM(CASE WHEN fal.is_test_file = TRUE THEN 1 ELSE 0 END) as test_files_modified,
            SUM(CASE WHEN fal.is_documentation_file = TRUE THEN 1 ELSE 0 END) as doc_files_modified,
            ROUND(
                (SUM(CASE WHEN fal.is_test_file = TRUE THEN 1 ELSE 0 END) * 100.0) / 
                NULLIF(COUNT(*), 0), 1
            ) as test_modification_percentage,
            COUNT(DISTINCT gal.commit_hash) as total_commits,
            AVG(gal.files_changed) as avg_files_per_commit,
            CASE 
                WHEN COUNT(DISTINCT fal.component_id) > 5 AND 
                     ROUND((SUM(CASE WHEN fal.is_test_file = TRUE THEN 1 ELSE 0 END) * 100.0) / NULLIF(COUNT(*), 0), 1) > 20 
                THEN 'HIGH_VELOCITY_GOOD_TESTING'
                WHEN COUNT(DISTINCT fal.component_id) > 5 AND 
                     ROUND((SUM(CASE WHEN fal.is_test_file = TRUE THEN 1 ELSE 0 END) * 100.0) / NULLIF(COUNT(*), 0), 1) < 10 
                THEN 'HIGH_VELOCITY_LOW_TESTING' 
                WHEN COUNT(DISTINCT fal.component_id) < 2 THEN 'LOW_VELOCITY'
                ELSE 'MODERATE_VELOCITY'
            END as velocity_assessment
        FROM file_activity_log fal
        LEFT JOIN git_activity_log gal ON date(fal.timestamp) = date(gal.timestamp)
        WHERE fal.timestamp > datetime('now', '-7 days')
        """,
        
        # Active drift alerts summary
        """
        CREATE VIEW IF NOT EXISTS active_drift_alerts_summary AS
        SELECT 
            alert_type,
            severity,
            COUNT(*) as alert_count,
            MIN(detected_at) as oldest_alert,
            MAX(detected_at) as newest_alert,
            AVG(julianday('now') - julianday(detected_at)) as avg_age_days,
            GROUP_CONCAT(DISTINCT component_id) as affected_components
        FROM current_drift_alerts 
        WHERE is_active = TRUE
        GROUP BY alert_type, severity
        ORDER BY 
            CASE severity 
                WHEN 'CRITICAL' THEN 1 
                WHEN 'HIGH' THEN 2 
                WHEN 'MEDIUM' THEN 3 
                WHEN 'LOW' THEN 4 
            END,
            alert_count DESC
        """,
        
        # File activity trends
        """
        CREATE VIEW IF NOT EXISTS file_activity_trends AS
        SELECT 
            date(timestamp) as activity_date,
            COUNT(*) as total_changes,
            COUNT(DISTINCT file_path) as unique_files_changed,
            COUNT(DISTINCT component_id) as components_affected,
            SUM(CASE WHEN change_type = 'created' THEN 1 ELSE 0 END) as files_created,
            SUM(CASE WHEN change_type = 'modified' THEN 1 ELSE 0 END) as files_modified,
            SUM(CASE WHEN change_type = 'deleted' THEN 1 ELSE 0 END) as files_deleted,
            SUM(CASE WHEN is_test_file = TRUE THEN 1 ELSE 0 END) as test_changes,
            SUM(CASE WHEN is_documentation_file = TRUE THEN 1 ELSE 0 END) as doc_changes,
            ROUND(
                (SUM(CASE WHEN is_test_file = TRUE THEN 1 ELSE 0 END) * 100.0) / NULLIF(COUNT(*), 0), 1
            ) as test_change_percentage
        FROM file_activity_log 
        WHERE timestamp > datetime('now', '-30 days')
        GROUP BY date(timestamp)
        ORDER BY activity_date DESC
        """
    ]
    
    # Create all views
    for view_sql in views:
        try:
            conn.execute(view_sql)
            view_name = view_sql.split("CREATE VIEW IF NOT EXISTS ")[1].split(" AS")[0]
            print(f"   ✅ Created view: {view_name}")
        except Exception as e:
            print(f"   ❌ Failed to create view: {e}")
    
    # ============ STORE FILE WATCHER SCRIPT IN DATABASE ============
    
    file_watcher_script = '''
import os
import sqlite3
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from datetime import datetime
import re
import subprocess
import json

class ProjectFileHandler(FileSystemEventHandler):
    def __init__(self, db_path):
        self.db_path = db_path
        self.project_root = os.getcwd()
        
    def get_component_id(self, file_path):
        """Map file path to component ID - simplified heuristic"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute(
            "SELECT component_id FROM components WHERE ? LIKE '%' || LOWER(component_name) || '%'", 
            (file_path.lower(),)
        )
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else None
        
    def analyze_file(self, file_path):
        """Extract metrics from file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            metrics = {
                'lines_of_code': len([line for line in content.split('\\n') if line.strip()]),
                'import_count': len(re.findall(r'^\\s*(import|from|require)', content, re.MULTILINE)),
                'function_count': len(re.findall(r'def\\s+\\w+|function\\s+\\w+', content)),
                'class_count': len(re.findall(r'class\\s+\\w+', content)),
                'is_test_file': 'test' in file_path.lower(),
                'is_documentation_file': file_path.endswith(('.md', '.rst', '.txt'))
            }
            return metrics
        except:
            return {}
    
    def update_database(self, file_path, event_type):
        """Update database with file change"""
        try:
            conn = sqlite3.connect(self.db_path)
            
            # Get file info
            file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
            file_name = os.path.basename(file_path)
            file_extension = os.path.splitext(file_name)[1]
            component_id = self.get_component_id(file_path)
            
            # Analyze file if it exists
            metrics = self.analyze_file(file_path) if os.path.exists(file_path) else {}
            
            # Insert into activity log
            conn.execute("""
                INSERT INTO file_activity_log 
                (file_path, file_name, file_extension, change_type, file_size_bytes, 
                 lines_of_code, component_id, is_test_file, is_documentation_file)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                file_path, file_name, file_extension, event_type, file_size,
                metrics.get('lines_of_code', 0), component_id,
                metrics.get('is_test_file', False), metrics.get('is_documentation_file', False)
            ))
            
            # Update/insert current file status
            if os.path.exists(file_path):
                conn.execute("""
                    INSERT OR REPLACE INTO current_file_status
                    (file_path, file_name, file_extension, component_id, current_size_bytes,
                     current_lines_of_code, is_test_file, is_documentation_file, last_modified,
                     import_count, function_count, class_count)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), ?, ?, ?)
                """, (
                    file_path, file_name, file_extension, component_id, file_size,
                    metrics.get('lines_of_code', 0), metrics.get('is_test_file', False),
                    metrics.get('is_documentation_file', False), metrics.get('import_count', 0),
                    metrics.get('function_count', 0), metrics.get('class_count', 0)
                ))
            else:
                # File was deleted
                conn.execute("DELETE FROM current_file_status WHERE file_path = ?", (file_path,))
            
            # Check for drift conditions and create alerts
            self.check_drift_conditions(conn, component_id)
            
            conn.commit()
            conn.close()
            
            print(f"📊 {datetime.now().strftime('%H:%M:%S')} - {event_type}: {file_path}")
            
        except Exception as e:
            print(f"❌ Error updating database: {e}")
    
    def check_drift_conditions(self, conn, component_id):
        """Check for drift conditions and create alerts"""
        if not component_id:
            return
            
        # Check test coverage drift
        cursor = conn.execute("""
            SELECT 
                COUNT(CASE WHEN is_test_file = FALSE THEN 1 END) as impl_files,
                COUNT(CASE WHEN is_test_file = TRUE THEN 1 END) as test_files
            FROM current_file_status WHERE component_id = ?
        """, (component_id,))
        impl_files, test_files = cursor.fetchone()
        
        if impl_files > 0:
            test_ratio = (test_files / impl_files) * 100
            if test_ratio < 50:  # Less than 50% test coverage
                conn.execute("""
                    INSERT OR REPLACE INTO current_drift_alerts
                    (alert_type, severity, component_id, alert_title, alert_description, 
                     threshold_value, current_value, is_active)
                    VALUES ('LOW_TEST_COVERAGE', 'MEDIUM', ?, 'Low Test Coverage Detected',
                            'Test file ratio is below recommended threshold', 50, ?, TRUE)
                """, (component_id, test_ratio))
    
    def on_modified(self, event):
        if not event.is_directory and self.should_track(event.src_path):
            self.update_database(event.src_path, 'modified')
    
    def on_created(self, event):
        if not event.is_directory and self.should_track(event.src_path):
            self.update_database(event.src_path, 'created')
    
    def on_deleted(self, event):
        if not event.is_directory and self.should_track(event.src_path):
            self.update_database(event.src_path, 'deleted')
    
    def should_track(self, file_path):
        """Determine if file should be tracked"""
        ignore_patterns = [
            '.git/', '__pycache__/', '.pytest_cache/', 'node_modules/',
            '.venv/', 'venv/', '.db', '.sqlite', '.log'
        ]
        return not any(pattern in file_path for pattern in ignore_patterns)

def start_file_watcher():
    """Start the file watcher"""
    db_path = "neuroca_temporal_analysis.db"
    
    if not os.path.exists(db_path):
        print(f"❌ Database not found: {db_path}")
        return
    
    print("🚀 STARTING AUTOMATED PROJECT MONITORING")
    print("=" * 50)
    print(f"📊 Database: {db_path}")
    print(f"📁 Watching: {os.getcwd()}")
    print("🔄 Monitoring file changes in real-time...")
    print("💡 Press Ctrl+C to stop")
    print()
    
    event_handler = ProjectFileHandler(db_path)
    observer = Observer()
    observer.schedule(event_handler, os.getcwd(), recursive=True)
    
    try:
        observer.start()
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\\n🛑 Stopping file watcher...")
        observer.stop()
    
    observer.join()
    print("✅ File watcher stopped")

if __name__ == "__main__":
    start_file_watcher()
'''
    
    # Store the file watcher script in database
    try:
        conn.execute("""
            INSERT OR REPLACE INTO automation_scripts 
            (script_name, script_description, script_code, script_type)
            VALUES (?, ?, ?, ?)
        """, (
            'file_watcher',
            'Real-time file monitoring script that updates database on every file change',
            file_watcher_script,
            'File Watcher'
        ))
        print(f"   ✅ Stored file watcher script in database")
    except Exception as e:
        print(f"   ❌ Failed to store script: {e}")
    
    # ============ INITIALIZE CURRENT PROJECT METRICS ============
    
    initial_metrics = [
        ('total_components', 49, 'count', 40, 45),
        ('completion_percentage', 79.6, 'percentage', 70, 75),
        ('test_coverage_average', 85, 'percentage', 80, 70),
        ('critical_bugs', 0, 'count', 1, 3),
        ('documentation_coverage', 60, 'percentage', 70, 50),
        ('code_complexity_average', 8, 'score', 12, 15)
    ]
    
    for name, value, unit, warning, critical in initial_metrics:
        try:
            conn.execute("""
                INSERT OR REPLACE INTO current_project_metrics
                (metric_name, metric_value, metric_unit, threshold_warning, threshold_critical, baseline_value)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (name, value, unit, warning, critical, value))
        except Exception as e:
            print(f"   ❌ Failed to insert metric {name}: {e}")
    
    conn.commit()
    conn.close()
    
    print(f"\n🎉 AUTOMATED PROJECT TRACKING SYSTEM CREATED!")
    print(f"   📊 Database: neuroca_temporal_analysis.db (enhanced)")
    print(f"   📋 New Tables: 8 tables for automated data collection")
    print(f"   📈 New Views: 5 views for real-time analysis")
    print(f"   🤖 Monitoring Script: Stored in database for portability")
    print()
    print("🚀 TO START MONITORING:")
    print("   1. Install required package: pip install watchdog")
    print("   2. Extract and run stored script:")
    print("      python -c \"import sqlite3; exec(sqlite3.connect('neuroca_temporal_analysis.db').execute('SELECT script_code FROM automation_scripts WHERE script_name = \\\"file_watcher\\\"').fetchone()[0])\"")
    print()
    print("📊 DBEAVER VIEWS TO MONITOR:")
    print("   • realtime_project_health - Overall project health")
    print("   • scope_drift_dashboard - Scope creep detection")
    print("   • progress_velocity_analysis - Development velocity")
    print("   • active_drift_alerts_summary - Active issues")
    print("   • file_activity_trends - Activity patterns")
    
    return True

if __name__ == "__main__":
    create_automated_tracking_system()
