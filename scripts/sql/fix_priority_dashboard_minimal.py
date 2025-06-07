#!/usr/bin/env python3
"""
Fix priority_dashboard - remove unwanted file tracking columns
"""

import sqlite3

def fix_priority_dashboard_minimal():
    """Create minimal priority_dashboard without file count columns."""
    
    print("🎯 FIXING PRIORITY DASHBOARD (MINIMAL VERSION)")
    print("=" * 50)
    
    conn = sqlite3.connect("neuroca_temporal_analysis.db")
    
    # Drop existing priority_dashboard view
    try:
        conn.execute("DROP VIEW IF EXISTS priority_dashboard")
        print("   ✅ Removed old priority_dashboard view")
    except Exception as e:
        print(f"   ❌ Error dropping old view: {e}")
    
    # Create minimal priority_dashboard - no file count columns
    minimal_dashboard = """
    CREATE VIEW priority_dashboard AS
    SELECT 
        c.component_name,
        s.status_name as status,
        c.priority,
        CASE WHEN s.status_name = 'Completed' THEN 100.0 
             WHEN s.status_name = 'In Progress' THEN 75.0 
             WHEN s.status_name = 'Testing' THEN 85.0
             WHEN s.status_name = 'Planned' THEN 25.0
             ELSE 50.0 END as completion_percentage,
        c.effort_hours,
        
        -- Activity level (derived from file tracking but no raw counts shown)
        CASE 
            WHEN (SELECT COUNT(*) FROM file_activity_log fal 
                  WHERE fal.component_id = c.component_id 
                  AND fal.timestamp > datetime('now', '-7 days')) > 10 THEN 'Very Active'
            WHEN (SELECT COUNT(*) FROM file_activity_log fal 
                  WHERE fal.component_id = c.component_id 
                  AND fal.timestamp > datetime('now', '-7 days')) > 3 THEN 'Active'
            WHEN (SELECT COUNT(*) FROM file_activity_log fal 
                  WHERE fal.component_id = c.component_id 
                  AND fal.timestamp > datetime('now', '-7 days')) > 0 THEN 'Some Activity'
            ELSE 'Inactive'
        END as activity_level,
        
        -- Test coverage (derived from file tracking but no raw counts shown)
        CASE 
            WHEN (SELECT COUNT(*) FROM file_activity_log fal 
                  WHERE fal.component_id = c.component_id 
                  AND fal.is_test_file = TRUE 
                  AND fal.timestamp > datetime('now', '-7 days')) > 0 THEN 'Has Tests'
            ELSE 'No Tests'
        END as test_coverage_status,
        
        c.updated_at as last_updated

    FROM components c 
    LEFT JOIN statuses s ON c.status_id = s.status_id
    WHERE c.is_active = TRUE
    ORDER BY 
        CASE c.priority 
            WHEN 'Critical' THEN 1
            WHEN 'High' THEN 2  
            WHEN 'Medium' THEN 3
            WHEN 'Low' THEN 4
            ELSE 5
        END,
        CASE 
            WHEN (SELECT COUNT(*) FROM file_activity_log fal 
                  WHERE fal.component_id = c.component_id 
                  AND fal.timestamp > datetime('now', '-7 days')) > 10 THEN 1
            WHEN (SELECT COUNT(*) FROM file_activity_log fal 
                  WHERE fal.component_id = c.component_id 
                  AND fal.timestamp > datetime('now', '-7 days')) > 3 THEN 2
            WHEN (SELECT COUNT(*) FROM file_activity_log fal 
                  WHERE fal.component_id = c.component_id 
                  AND fal.timestamp > datetime('now', '-7 days')) > 0 THEN 3
            ELSE 4
        END,
        c.component_name
    """
    
    try:
        conn.execute(minimal_dashboard)
        conn.commit()
        print("   ✅ Created minimal priority_dashboard")
        
        # Test the new view
        cursor = conn.execute("SELECT COUNT(*) FROM priority_dashboard")
        count = cursor.fetchone()[0]
        print(f"   📊 Dashboard shows {count} components")
        
        # Show sample of minimal data
        print(f"\n📋 MINIMAL DASHBOARD SAMPLE:")
        cursor = conn.execute("""
            SELECT component_name, status, priority, completion_percentage, activity_level, test_coverage_status
            FROM priority_dashboard 
            LIMIT 5
        """)
        
        results = cursor.fetchall()
        for row in results:
            name, status, priority, completion, activity, tests = row
            print(f"   {name}")
            print(f"      Status: {status} | Priority: {priority} | Completion: {completion}%")
            print(f"      Activity: {activity} | Tests: {tests}")
            print()
        
    except Exception as e:
        print(f"   ❌ Error creating minimal dashboard: {e}")
        return False
    
    conn.close()
    
    print("✅ MINIMAL PRIORITY DASHBOARD CREATED!")
    print("   🗂️  Just essential component data")
    print("   🚫 No file count columns (files_changed_today, files_changed_week, etc.)")
    print("   ✅ Still has activity_level and test_coverage_status (derived)")
    print("   📊 Clean, focused view")
    print()
    print("📋 IN DBEAVER:")
    print("   Refresh: priority_dashboard")
    print("   Clean component list without clutter!")
    
    return True

if __name__ == "__main__":
    fix_priority_dashboard_minimal()
