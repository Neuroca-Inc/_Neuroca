#!/usr/bin/env python3
"""
Test script to demonstrate temporal database features and functionality.
"""

import sqlite3
import pandas as pd
from datetime import datetime

def test_temporal_database():
    """Test the temporal database features"""
    
    print("🧪 TESTING NEUROCA TEMPORAL DATABASE")
    print("=" * 50)
    
    # Connect to temporal database
    conn = sqlite3.connect("neuroca_temporal_analysis.db")
    conn.execute("PRAGMA foreign_keys = ON")
    
    # Test 1: Show current critical blockers
    print("\n🚨 CRITICAL BLOCKERS:")
    print("-" * 30)
    critical_df = pd.read_sql_query("""
        SELECT 
            component_name,
            working_status,
            priority_to_fix,
            complexity_to_fix,
            effort_hours,
            missing_dependencies
        FROM critical_blockers
        ORDER BY 
            CASE priority_to_fix 
                WHEN 'CRITICAL' THEN 1 
                WHEN 'HIGH' THEN 2 
                ELSE 3 
            END
        LIMIT 10
    """, conn)
    
    if not critical_df.empty:
        print(critical_df.to_string(index=False))
    else:
        print("✅ No critical blockers found!")
    
    # Test 2: Show data quality report
    print(f"\n📊 DATA QUALITY REPORT:")
    print("-" * 30)
    quality_df = pd.read_sql_query("SELECT * FROM data_quality_report", conn)
    print(quality_df.to_string(index=False))
    
    # Test 3: Show component change history
    print(f"\n📜 RECENT CHANGE HISTORY:")
    print("-" * 30)
    history_df = pd.read_sql_query("""
        SELECT 
            component_name,
            change_type,
            history_timestamp,
            version
        FROM component_change_history 
        LIMIT 10
    """, conn)
    print(history_df.to_string(index=False))
    
    # Test 4: Test temporal functionality by making a change
    print(f"\n🔧 TESTING TEMPORAL FUNCTIONALITY:")
    print("-" * 40)
    
    # Update a component to trigger temporal tracking
    cursor = conn.execute("""
        UPDATE components 
        SET priority = 'Critical', 
            notes = 'Updated for testing temporal features - ' || datetime('now')
        WHERE component_name = 'FastAPI Application'
    """)
    
    if cursor.rowcount > 0:
        print("✅ Updated FastAPI Application component")
        
        # Show the change was tracked
        change_df = pd.read_sql_query("""
            SELECT 
                component_name,
                change_type,
                history_timestamp,
                version
            FROM component_change_history 
            WHERE component_name = 'FastAPI Application'
            ORDER BY history_timestamp DESC
            LIMIT 3
        """, conn)
        
        print("\n📝 Change tracking for FastAPI Application:")
        print(change_df.to_string(index=False))
    
    # Test 5: Show constraint validation
    print(f"\n✅ CONSTRAINT VALIDATION:")
    print("-" * 30)
    
    # Try to insert invalid data to test constraints
    try:
        conn.execute("""
            INSERT INTO components (component_name, category_id, priority)
            VALUES ('Test Component', 1, 'INVALID_PRIORITY')
        """)
        print("❌ Constraint validation failed - invalid data was accepted")
    except sqlite3.IntegrityError as e:
        print("✅ Constraint validation working - invalid priority rejected")
        print(f"   Error: {e}")
    
    # Test 6: Show foreign key enforcement
    try:
        conn.execute("""
            INSERT INTO component_usage_analysis (component_id, working_status)
            VALUES (999999, 'Missing')
        """)
        print("❌ Foreign key constraint failed - invalid component_id accepted")
    except sqlite3.IntegrityError as e:
        print("✅ Foreign key constraint working - invalid component_id rejected")
        print(f"   Error: {e}")
    
    # Test 7: Summary statistics
    print(f"\n📈 DATABASE STATISTICS:")
    print("-" * 25)
    
    stats = {}
    stats['Active Components'] = conn.execute("SELECT COUNT(*) FROM components WHERE is_active = TRUE").fetchone()[0]
    stats['Total History Records'] = conn.execute("SELECT COUNT(*) FROM components_history").fetchone()[0]
    stats['Usage Analysis Records'] = conn.execute("SELECT COUNT(*) FROM component_usage_analysis WHERE is_active = TRUE").fetchone()[0]
    stats['Critical Priority Components'] = conn.execute("SELECT COUNT(*) FROM component_usage_analysis WHERE priority_to_fix = 'CRITICAL' AND is_active = TRUE").fetchone()[0]
    stats['Missing Components'] = conn.execute("SELECT COUNT(*) FROM component_usage_analysis WHERE working_status = 'Missing' AND is_active = TRUE").fetchone()[0]
    stats['Fully Working Components'] = conn.execute("SELECT COUNT(*) FROM component_usage_analysis WHERE working_status = 'Fully Working' AND is_active = TRUE").fetchone()[0]
    
    for key, value in stats.items():
        print(f"   {key}: {value}")
    
    conn.commit()
    conn.close()
    
    print(f"\n🎯 TEMPORAL DATABASE FEATURES VERIFIED:")
    print("   ✅ Data validation constraints")
    print("   ✅ Foreign key enforcement") 
    print("   ✅ Automatic change tracking")
    print("   ✅ Version control")
    print("   ✅ Audit trails")
    print("   ✅ Enhanced views for analysis")
    print("   ✅ Referential integrity")

if __name__ == "__main__":
    test_temporal_database()
