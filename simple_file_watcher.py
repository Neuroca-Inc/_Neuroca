#!/usr/bin/env python3
"""
Simple standalone file watcher for project tracking
"""

import os
import sqlite3
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from datetime import datetime

class ProjectFileHandler(FileSystemEventHandler):
    def __init__(self, db_path):
        self.db_path = db_path
        
    def get_component_id(self, file_path):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.execute(
                "SELECT component_id FROM components WHERE ? LIKE '%' || LOWER(component_name) || '%' LIMIT 1", 
                (file_path.lower(),)
            )
            result = cursor.fetchone()
            conn.close()
            return result[0] if result else None
        except:
            return None
        
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
            else:
                conn.execute("DELETE FROM current_file_status WHERE file_path = ?", (file_path,))
            
            conn.commit()
            conn.close()
            print(f"📊 {datetime.now().strftime('%H:%M:%S')} - {event_type}: {file_path}")
        except Exception as e:
            print(f"❌ Database error: {e}")
    
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
        ignore = ['.git/', '__pycache__/', '.db', '.sqlite', '.log', '.pyc', 'node_modules/']
        return not any(pattern in file_path for pattern in ignore)

def start_watcher():
    db_path = "neuroca_temporal_analysis.db"
    if not os.path.exists(db_path):
        print(f"❌ Database not found: {db_path}")
        return
    
    print("🚀 STARTING SIMPLE FILE WATCHER")
    print(f"📊 Database: {db_path}")
    print(f"📁 Watching: {os.getcwd()}")
    print("💡 Press Ctrl+C to stop monitoring")
    print()
    
    handler = ProjectFileHandler(db_path)
    observer = Observer()
    observer.schedule(handler, os.getcwd(), recursive=True)
    
    try:
        observer.start()
        print("✅ File watcher is now running...")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        print("\n🛑 Stopping file watcher...")
    
    observer.join()
    print("✅ File watcher stopped")

if __name__ == "__main__":
    start_watcher()
