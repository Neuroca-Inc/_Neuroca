#!/usr/bin/env python3
"""
Check database structure to fix the dashboard
"""

import sqlite3

def check_structure():
    """Check database structure."""
    
    conn = sqlite3.connect("neuroca_temporal_analysis.db")
    
    print("📊 DATABASE STRUCTURE CHECK")
    print("=" * 50)
    
    # Get all tables
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    
    print(f"\n📋 EXISTING TABLES ({len(tables)}):")
    for table in tables:
        print(f"   - {table[0]}")
    
    # Check if components table exists and its structure
    try:
        cursor = conn.execute("PRAGMA table_info(components)")
        columns = cursor.fetchall()
        if columns:
            print(f"\n🔧 COMPONENTS TABLE STRUCTURE:")
            for col in columns:
                print(f"   {col[1]} ({col[2]})")
        else:
            print(f"\n❌ No components table found")
    except Exception as e:
        print(f"\n❌ Error checking components table: {e}")
    
    # Check if we have data in file_activity_log
    try:
        cursor = conn.execute("SELECT COUNT(*) FROM file_activity_log")
        count = cursor.fetchone()[0]
        print(f"\n📁 FILE_ACTIVITY_LOG: {count} records")
        
        if count > 0:
            cursor = conn.execute("SELECT file_path, change_type, timestamp FROM file_activity_log ORDER BY timestamp DESC LIMIT 3")
            recent = cursor.fetchall()
            print("   Recent activity:")
            for row in recent:
                print(f"     {row[2]}: {row[1]} {row[0]}")
    except Exception as e:
        print(f"\n❌ Error checking file_activity_log: {e}")
    
    conn.close()

if __name__ == "__main__":
    check_structure()
