#!/usr/bin/env python3
"""
Simple script to start the file watcher from the database
"""

import sqlite3
import os
import sys

def start_watcher():
    """Extract and run the file watcher script from database."""
    
    db_path = "neuroca_temporal_analysis.db"
    
    if not os.path.exists(db_path):
        print(f"❌ Database not found: {db_path}")
        print("   Run 'python run_automated_tracking_setup.py' first")
        return False
    
    try:
        # Check if watchdog is installed
        import watchdog
        print("✅ Watchdog library found")
    except ImportError:
        print("❌ Watchdog library not found")
        print("   Install with: pip install watchdog")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.execute(
            "SELECT script_code FROM automation_scripts WHERE script_name = 'file_watcher'"
        )
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            print("❌ File watcher script not found in database")
            return False
        
        script_code = result[0]
        print("🚀 Starting file watcher from database...")
        print("   Press Ctrl+C to stop monitoring")
        print()
        
        # Execute the stored script
        exec(script_code)
        
    except Exception as e:
        print(f"❌ Error starting file watcher: {e}")
        return False
    
    return True

if __name__ == "__main__":
    start_watcher()
