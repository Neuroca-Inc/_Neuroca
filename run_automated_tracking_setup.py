#!/usr/bin/env python3
"""
Run the automated project tracking system setup
"""

import sqlite3
from datetime import datetime
import os

def run_setup():
    """Run the automated project tracking setup."""
    
    print("🚀 CREATING AUTOMATED PROJECT TRACKING SYSTEM")
    print("=" * 65)
    
    # Connect to existing database
    conn = sqlite3.connect("neuroca_temporal_analysis.db")
    conn.execute("PRAGMA foreign_keys = ON")
    
    # Create tables for automated tracking
    tables = [
        """
        CREATE TABLE IF NOT EXISTS automation_scripts (
            script_id INTEGER PRIMARY KEY,
            script_name TEXT NOT NULL UNIQUE,
            script_description TEXT,
            script_code TEXT NOT NULL,
            script_type TEXT,
            is_active BOOLEAN DEFAULT TRUE,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """,
        
        """
        CREATE TABLE IF NOT EXISTS file_activity_log (
            activity_id INTEGER PRIMARY KEY,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            file_path TEXT NOT NULL,
            file_name TEXT,
            change_type TEXT,
            file_size_bytes INTEGER,
            component_id INTEGER,
            is_test_file BOOLEAN DEFAULT FALSE,
            FOREIGN KEY (component_id) REFERENCES components(component_id)
        )
        """,
        
        """
        CREATE TABLE IF NOT EXISTS current_file_status (
            file_id INTEGER PRIMARY KEY,
            file_path TEXT NOT NULL UNIQUE,
            file_name TEXT,
            component_id INTEGER,
            current_size_bytes INTEGER,
            is_test_file BOOLEAN DEFAULT FALSE,
            last_modified DATETIME,
            FOREIGN KEY (component_id) REFERENCES components(component_id)
        )
        """,
        
        """
        CREATE TABLE IF NOT EXISTS current_drift_alerts (
            alert_id INTEGER PRIMARY KEY,
            alert_type TEXT NOT NULL,
            severity TEXT,
            component_id INTEGER,
            alert_title TEXT NOT NULL,
            alert_description TEXT,
            detected_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            is_active BOOLEAN DEFAULT TRUE,
            FOREIGN KEY (component_id) REFERENCES components(component_id)
        )
        """
    ]
    
    # Create tables
    for i, table_sql in enumerate(tables, 1):
        try:
            conn.execute(table_sql)
            table_name = table_sql.split("CREATE TABLE IF NOT EXISTS ")[1].split(" (")[0]
            print(f"   ✅ {i:2d}. Created table: {table_name}")
        except Exception as e:
            print(f"   ❌ {i:2d}. Failed to create table: {e}")
    
    # Create views for real-time monitoring
    views = [
        """
        CREATE VIEW IF NOT EXISTS realtime_project_health AS
        SELECT 
            COUNT(DISTINCT c.component_id) as total_components,
            COUNT(DISTINCT CASE WHEN cfs.last_modified > datetime('now', '-7 days') THEN c.component_id END) as active_components,
            COUNT(CASE WHEN cda.is_active = TRUE THEN 1 END) as active_alerts,
            datetime('now') as last_updated
        FROM components c
        LEFT JOIN current_file_status cfs ON c.component_id = cfs.component_id
        LEFT JOIN current_drift_alerts cda ON c.component_id = cda.component_id
        WHERE c.is_active = TRUE
        """,
        
        """
        CREATE VIEW IF NOT EXISTS file_activity_summary AS
        SELECT 
            date(timestamp) as activity_date,
            COUNT(*) as total_changes,
            COUNT(DISTINCT file_path) as files_changed,
            COUNT(CASE WHEN change_type = 'created' THEN 1 END) as files_created,
            COUNT(CASE WHEN change_type = 'modified' THEN 1 END) as files_modified,
            COUNT(CASE WHEN is_test_file = TRUE THEN 1 END) as test_changes
        FROM file_activity_log 
        WHERE timestamp > datetime('now', '-30 days')
        GROUP BY date(timestamp)
        ORDER BY activity_date DESC
        """
    ]
    
    # Create views
    for view_sql in views:
        try:
            conn.execute(view_sql)
            view_name = view_sql.split("CREATE VIEW IF NOT EXISTS ")[1].split(" AS")[0]
            print(f"   ✅ Created view: {view_name}")
        except Exception as e:
            print(f"   ❌ Failed to create view: {e}")
    
    # Store a simple file watcher script
    file_watcher_script = '''import os
import sqlite3
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from datetime import datetime

class ProjectFileHandler(FileSystemEventHandler):
    def __init__(self, db_path):
        self.db_path = db_path
        
    def get_component_id(self, file_path):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute(
            "SELECT component_id FROM components WHERE ? LIKE '%' || LOWER(component_name) || '%' LIMIT 1", 
            (file_path.lower(),)
        )
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else None
        
    def update_database(self, file_path, event_type):
        try:
            conn = sqlite3.connect(self.db_path)
            file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
            file_name = os.path.basename(file_path)
            component_id = self.get_component_id(file_path)
            is_test = 'test' in file_path.lower()
            
            # Insert into activity log
            conn.execute(
                "INSERT INTO file_activity_log (file_path, file_name, change_type, file_size_bytes, component_id, is_test_file) VALUES (?, ?, ?, ?, ?, ?)",
                (file_path, file_name, event_type, file_size, component_id, is_test)
            )
            
            # Update current status
            if os.path.exists(file_path):
                conn.execute(
                    "INSERT OR REPLACE INTO current_file_status (file_path, file_name, component_id, current_size_bytes, is_test_file, last_modified) VALUES (?, ?, ?, ?, ?, datetime('now'))",
                    (file_path, file_name, component_id, file_size, is_test)
                )
            
            conn.commit()
            conn.close()
            print(f"📊 {datetime.now().strftime('%H:%M:%S')} - {event_type}: {file_path}")
        except Exception as e:
            print(f"❌ Error: {e}")
    
    def on_modified(self, event):
        if not event.is_directory and self.should_track(event.src_path):
            self.update_database(event.src_path, 'modified')
    
    def on_created(self, event):
        if not event.is_directory and self.should_track(event.src_path):
            self.update_database(event.src_path, 'created')
    
    def should_track(self, file_path):
        ignore = ['.git/', '__pycache__/', '.db', '.sqlite', '.log']
        return not any(pattern in file_path for pattern in ignore)

def start_watcher():
    db_path = "neuroca_temporal_analysis.db"
    if not os.path.exists(db_path):
        print(f"❌ Database not found: {db_path}")
        return
    
    print("🚀 STARTING FILE WATCHER")
    print(f"📊 Database: {db_path}")
    print(f"📁 Watching: {os.getcwd()}")
    print("Press Ctrl+C to stop")
    
    handler = ProjectFileHandler(db_path)
    observer = Observer()
    observer.schedule(handler, os.getcwd(), recursive=True)
    
    try:
        observer.start()
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        print("\\nStopped watcher")
    
    observer.join()

if __name__ == "__main__":
    start_watcher()
'''
    
    # Store the script in database
    try:
        conn.execute(
            "INSERT OR REPLACE INTO automation_scripts (script_name, script_description, script_code, script_type) VALUES (?, ?, ?, ?)",
            ('file_watcher', 'Real-time file monitoring script', file_watcher_script, 'File Watcher')
        )
        print("   ✅ Stored file watcher script in database")
    except Exception as e:
        print(f"   ❌ Failed to store script: {e}")
    
    conn.commit()
    conn.close()
    
    print(f"\n🎉 AUTOMATED TRACKING SYSTEM CREATED!")
    print(f"   📊 Database: neuroca_temporal_analysis.db (enhanced)")
    print(f"   🤖 Monitoring Script: Stored in database")
    print()
    print("🚀 TO START MONITORING:")
    print("   1. Install: pip install watchdog")
    print('   2. Run: python -c "import sqlite3; exec(sqlite3.connect(\'neuroca_temporal_analysis.db\').execute(\'SELECT script_code FROM automation_scripts WHERE script_name = \\"file_watcher\\"\').fetchone()[0])"')
    print()
    print("📊 MONITOR IN DBEAVER:")
    print("   • realtime_project_health - Current status")
    print("   • file_activity_summary - Recent activity")
    print("   • current_drift_alerts - Active issues")
    
    return True

if __name__ == "__main__":
    run_setup()
