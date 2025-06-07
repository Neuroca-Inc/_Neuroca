#!/usr/bin/env python3
"""
Fix priority_dashboard cleanly - just add file tracking metrics to existing components
"""

import sqlite3

def fix_priority_dashboard_clean():
    """Create clean priority_dashboard with file tracking metrics."""
    
    print("🧹 FIXING PRIORITY DASHBOARD (CLEAN VERSION)")
    print("=" * 50)
    
    conn = sqlite3.connect("neuroca_temporal_analysis.db")
    
    # Drop existing priority_dashboard view
    try:
        conn.execute("DROP VIEW IF EXISTS priority_dashboard")
        print("   ✅ Removed cluttered priority_dashboard view")
    except Exception as e:
        print(f"   ❌ Error dropping old view: {e}")
    
    # Create clean priority_dashboard - just components with file metrics
    clean_dashboard = """
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
        
        -- File Activity Metrics (NEW - clean, no emojis)
        (SELECT COUNT(*) FROM file_activity_log fal 
         WHERE fal.component_id = c.component_id 
         AND fal.timestamp > datetime('now', '-24 hours')) as files_changed_today,
        
        (SELECT COUNT(*) FROM file_activity_log fal 
         WHERE fal.component_id = c.component_id 
         AND fal.timestamp > datetime('now', '-7 days')) as files_changed_week,
        
        (SELECT COUNT(*) FROM file_activity_log fal 
         WHERE fal.component_id = c.component_id 
         AND fal.is_test_file = TRUE 
         AND fal.timestamp > datetime('now', '-7 days')) as test_files_changed_week,
        
        -- Activity level (clean text)
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
        
        -- Test coverage (clean text)
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
        files_changed_week DESC,
        c.component_name
    """
    
    try:
        conn.execute(clean_dashboard)
        conn.commit()
        print("   ✅ Created clean priority_dashboard")
        
        # Test the new view
        cursor = conn.execute("SELECT COUNT(*) FROM priority_dashboard")
        count = cursor.fetchone()[0]
        print(f"   📊 Dashboard shows {count} components")
        
        # Show sample of clean data
        print(f"\n📋 CLEAN DASHBOARD SAMPLE:")
        cursor = conn.execute("""
            SELECT component_name, status, priority, files_changed_week, activity_level, test_coverage_status
            FROM priority_dashboard 
            LIMIT 5
        """)
        
        results = cursor.fetchall()
        for row in results:
            name, status, priority, files_week, activity, tests = row
            print(f"   {name}")
            print(f"      Status: {status} | Priority: {priority}")
            print(f"      Files this week: {files_week or 0} | Activity: {activity}")
            print(f"      Tests: {tests}")
            print()
        
    except Exception as e:
        print(f"   ❌ Error creating clean dashboard: {e}")
        return False
    
    conn.close()
    
    print("✅ CLEAN PRIORITY DASHBOARD CREATED!")
    print("   🗂️  Just your components with file tracking metrics")
    print("   🚫 No emojis in status fields")
    print("   🚫 No project health dashboard clutter")
    print("   📊 Clean professional data")
    print()
    print("📋 IN DBEAVER:")
    print("   Refresh: priority_dashboard")
    print("   Clean component list with file activity!")
    
    return True

if __name__ == "__main__":
    fix_priority_dashboard_clean()
