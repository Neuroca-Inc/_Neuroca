#!/usr/bin/env python3
"""
Fix priority_dashboard with correct table joins
"""

import sqlite3
from datetime import datetime

def fix_dashboard():
    """Fix priority_dashboard with correct table structure."""
    
    print("🔧 FIXING PRIORITY DASHBOARD WITH CORRECT JOINS")
    print("=" * 60)
    
    conn = sqlite3.connect("neuroca_temporal_analysis.db")
    
    # Drop existing priority_dashboard view
    try:
        conn.execute("DROP VIEW IF EXISTS priority_dashboard")
        print("   ✅ Removed old priority_dashboard view")
    except Exception as e:
        print(f"   ❌ Error dropping old view: {e}")
    
    # Create enhanced priority_dashboard with correct joins
    enhanced_dashboard = """
    CREATE VIEW priority_dashboard AS
    SELECT 
        'PROJECT_OVERVIEW' as section,
        'Project Health Dashboard' as metric_name,
        CASE 
            WHEN completion_percentage >= 80 THEN '🟢 EXCELLENT'
            WHEN completion_percentage >= 60 THEN '🟡 GOOD' 
            WHEN completion_percentage >= 40 THEN '🟠 NEEDS_ATTENTION'
            ELSE '🔴 CRITICAL'
        END as status,
        completion_percentage as current_value,
        target_completion as target_value,
        ROUND(
            (completion_percentage / NULLIF(target_completion, 0)) * 100, 1
        ) as achievement_percentage,
        datetime('now') as last_updated,
        
        -- File Activity Metrics (NEW)
        (SELECT COUNT(*) FROM file_activity_log WHERE timestamp > datetime('now', '-24 hours')) as files_changed_today,
        (SELECT COUNT(*) FROM file_activity_log WHERE timestamp > datetime('now', '-7 days')) as files_changed_week,
        (SELECT COUNT(DISTINCT component_id) FROM file_activity_log WHERE timestamp > datetime('now', '-7 days') AND component_id IS NOT NULL) as active_components_week,
        (SELECT COUNT(*) FROM file_activity_log WHERE is_test_file = TRUE AND timestamp > datetime('now', '-7 days')) as test_changes_week,
        (SELECT COUNT(*) FROM current_drift_alerts WHERE is_active = TRUE) as active_alerts,
        
        -- Development Velocity
        CASE 
            WHEN (SELECT COUNT(*) FROM file_activity_log WHERE timestamp > datetime('now', '-7 days')) > 50 THEN '🚀 HIGH_VELOCITY'
            WHEN (SELECT COUNT(*) FROM file_activity_log WHERE timestamp > datetime('now', '-7 days')) > 20 THEN '🏃 MODERATE_VELOCITY'
            WHEN (SELECT COUNT(*) FROM file_activity_log WHERE timestamp > datetime('now', '-7 days')) > 5 THEN '🚶 LOW_VELOCITY'
            ELSE '🐌 VERY_LOW'
        END as development_velocity,
        
        -- Test Coverage Health
        CASE 
            WHEN (SELECT COUNT(*) FROM file_activity_log WHERE is_test_file = TRUE AND timestamp > datetime('now', '-7 days')) * 100.0 / 
                 NULLIF((SELECT COUNT(*) FROM file_activity_log WHERE timestamp > datetime('now', '-7 days')), 0) > 30 THEN '✅ GOOD_TEST_COVERAGE'
            WHEN (SELECT COUNT(*) FROM file_activity_log WHERE is_test_file = TRUE AND timestamp > datetime('now', '-7 days')) * 100.0 / 
                 NULLIF((SELECT COUNT(*) FROM file_activity_log WHERE timestamp > datetime('now', '-7 days')), 0) > 15 THEN '⚠️ LOW_TEST_COVERAGE'
            ELSE '🚨 VERY_LOW_TEST_COVERAGE'
        END as test_coverage_health,
        
        -- Recent Activity Summary
        'Last 24h: ' || 
        (SELECT COUNT(*) FROM file_activity_log WHERE timestamp > datetime('now', '-24 hours')) || 
        ' changes, ' ||
        (SELECT COUNT(DISTINCT component_id) FROM file_activity_log WHERE timestamp > datetime('now', '-24 hours') AND component_id IS NOT NULL) ||
        ' components' as activity_summary

    FROM (
        SELECT 
            AVG(CASE WHEN s.status_name = 'Completed' THEN 100.0 
                     WHEN s.status_name = 'In Progress' THEN 75.0 
                     WHEN s.status_name = 'Testing' THEN 85.0
                     WHEN s.status_name = 'Planned' THEN 25.0
                     ELSE 50.0 END) as completion_percentage,
            85.0 as target_completion
        FROM components c 
        LEFT JOIN statuses s ON c.status_id = s.status_id
        WHERE c.is_active = TRUE
    )

    UNION ALL

    SELECT 
        'COMPONENT_STATUS' as section,
        c.component_name as metric_name,
        CASE 
            WHEN s.status_name = 'Completed' THEN '✅ DONE'
            WHEN s.status_name = 'In Progress' THEN '🔄 ACTIVE'
            WHEN s.status_name = 'Testing' THEN '🧪 TESTING'
            WHEN s.status_name = 'Planned' THEN '📋 PLANNED'
            ELSE '❓ ' || COALESCE(s.status_name, 'UNKNOWN')
        END as status,
        CASE WHEN s.status_name = 'Completed' THEN 100.0 
             WHEN s.status_name = 'In Progress' THEN 75.0 
             WHEN s.status_name = 'Testing' THEN 85.0
             WHEN s.status_name = 'Planned' THEN 25.0
             ELSE 50.0 END as current_value,
        100.0 as target_value,
        CASE WHEN s.status_name = 'Completed' THEN 100.0 
             WHEN s.status_name = 'In Progress' THEN 75.0 
             WHEN s.status_name = 'Testing' THEN 85.0
             WHEN s.status_name = 'Planned' THEN 25.0
             ELSE 50.0 END as achievement_percentage,
        COALESCE(c.updated_at, c.created_at, datetime('now')) as last_updated,
        
        -- File Activity for this component
        (SELECT COUNT(*) FROM file_activity_log fal WHERE fal.component_id = c.component_id AND fal.timestamp > datetime('now', '-24 hours')) as files_changed_today,
        (SELECT COUNT(*) FROM file_activity_log fal WHERE fal.component_id = c.component_id AND fal.timestamp > datetime('now', '-7 days')) as files_changed_week,
        1 as active_components_week,
        (SELECT COUNT(*) FROM file_activity_log fal WHERE fal.component_id = c.component_id AND fal.is_test_file = TRUE AND fal.timestamp > datetime('now', '-7 days')) as test_changes_week,
        (SELECT COUNT(*) FROM current_drift_alerts cda WHERE cda.component_id = c.component_id AND cda.is_active = TRUE) as active_alerts,
        
        CASE 
            WHEN (SELECT COUNT(*) FROM file_activity_log fal WHERE fal.component_id = c.component_id AND fal.timestamp > datetime('now', '-7 days')) > 10 THEN '🚀 VERY_ACTIVE'
            WHEN (SELECT COUNT(*) FROM file_activity_log fal WHERE fal.component_id = c.component_id AND fal.timestamp > datetime('now', '-7 days')) > 3 THEN '🏃 ACTIVE'
            WHEN (SELECT COUNT(*) FROM file_activity_log fal WHERE fal.component_id = c.component_id AND fal.timestamp > datetime('now', '-7 days')) > 0 THEN '🚶 SOME_ACTIVITY'
            ELSE '💤 INACTIVE'
        END as development_velocity,
        
        CASE 
            WHEN (SELECT COUNT(*) FROM file_activity_log fal WHERE fal.component_id = c.component_id AND fal.is_test_file = TRUE AND fal.timestamp > datetime('now', '-7 days')) > 0 THEN '✅ HAS_TESTS'
            ELSE '⚠️ NO_TESTS'
        END as test_coverage_health,
        
        'Files: ' || 
        (SELECT COUNT(*) FROM file_activity_log fal WHERE fal.component_id = c.component_id AND fal.timestamp > datetime('now', '-7 days')) ||
        ' changes this week' as activity_summary

    FROM components c 
    LEFT JOIN statuses s ON c.status_id = s.status_id
    WHERE c.is_active = TRUE
    ORDER BY 
        CASE section 
            WHEN 'PROJECT_OVERVIEW' THEN 1 
            WHEN 'COMPONENT_STATUS' THEN 2 
        END,
        current_value DESC
    """
    
    try:
        conn.execute(enhanced_dashboard)
        print("   ✅ Created enhanced priority_dashboard with file tracking")
        
        # Test the new view
        cursor = conn.execute("SELECT COUNT(*) FROM priority_dashboard")
        count = cursor.fetchone()[0]
        print(f"   📊 Dashboard now shows {count} items")
        
        # Show sample of new data
        print(f"\n📋 SAMPLE DASHBOARD DATA:")
        cursor = conn.execute("""
            SELECT section, metric_name, status, files_changed_week, development_velocity, test_coverage_health 
            FROM priority_dashboard 
            LIMIT 5
        """)
        
        results = cursor.fetchall()
        for row in results:
            section, name, status, files_week, velocity, test_health = row
            print(f"   {section}: {name} - {status}")
            print(f"      📁 Files changed: {files_week or 0} this week")
            print(f"      🚀 Velocity: {velocity or 'N/A'}")
            print(f"      🧪 Tests: {test_health or 'N/A'}")
            print()
        
    except Exception as e:
        print(f"   ❌ Error creating enhanced dashboard: {e}")
        return False
    
    conn.commit()
    conn.close()
    
    print("🎉 PRIORITY DASHBOARD ENHANCED!")
    print("   📊 Now includes real-time file tracking metrics")
    print("   🔄 Shows development velocity and test coverage")
    print("   📈 Activity summary for last 24h and 7 days")
    print("   🚨 Drift alerts integrated")
    print("   🔗 Proper table joins with statuses")
    print()
    print("📋 VIEW IN DBEAVER:")
    print("   Just refresh: priority_dashboard")
    print("   Single view with ALL metrics!")
    
    return True

if __name__ == "__main__":
    fix_dashboard()
