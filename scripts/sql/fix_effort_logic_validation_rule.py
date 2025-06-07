#!/usr/bin/env python3
"""
Fix Effort Logic Validation Rule to Exclude "Fully Working" Components
====================================================================

This script fixes the EFFORT_LOGIC validation rule to exclude "Fully Working" 
components from effort hours vs complexity mismatch detection, since completed 
components should logically have 0 effort hours regardless of their complexity.

Usage:
    python scripts/sql/fix_effort_logic_validation_rule.py
"""

import sqlite3
import sys
from pathlib import Path

def connect_database(db_path="neuroca_temporal_analysis.db"):
    """Connect to the temporal analysis database."""
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row  # Enable dict-like access
        return conn
    except sqlite3.Error as e:
        print(f"❌ Database connection failed: {e}")
        sys.exit(1)

def fix_effort_logic_validation():
    """Fix the effort logic validation rule to exclude 'Fully Working' components."""
    
    # SQL to drop and recreate the bug_detection_report view with fixed validation
    update_view_sql = """
    DROP VIEW IF EXISTS bug_detection_report;
    
    CREATE VIEW bug_detection_report AS
            -- Data Inconsistency Bugs
            SELECT
                'DATA_INCONSISTENCY' as alert_type,
                'HIGH' as severity,
                c.component_name,
                'Status mismatch: components.status (' || s.status_name || ') vs usage_analysis.working_status (' || ua.working_status || ')' as description,
                'MISMATCH_STATUS' as bug_category,
                datetime('now') as detected_at
            FROM components c
            JOIN statuses s ON c.status_id = s.status_id
            JOIN component_usage_analysis ua ON c.component_id = ua.component_id
            WHERE ua.is_active = TRUE
              AND c.is_active = TRUE
              AND ((s.status_name = 'Fully Working' AND ua.working_status != 'Fully Working')
                   OR (s.status_name != 'Fully Working' AND ua.working_status = 'Fully Working'))

            UNION ALL

            -- Effort Hours Logic Inconsistency (components marked "Fully Working" but still have effort hours)
            SELECT
                'EFFORT_HOURS_INCONSISTENCY' as alert_type,
                'MEDIUM' as severity,
                c.component_name,
                'Logic error: marked as "Fully Working" but still has ' || c.effort_hours || ' effort hours remaining' as description,
                'EFFORT_LOGIC_ERROR' as bug_category,
                datetime('now') as detected_at
            FROM components c
            JOIN statuses s ON c.status_id = s.status_id
            WHERE c.is_active = TRUE
              AND s.status_name = 'Fully Working'
              AND c.effort_hours > 0

            UNION ALL

            -- Logic Inconsistency Bugs
            SELECT
                'LOGIC_INCONSISTENCY' as alert_type,
                'MEDIUM' as severity,
                c.component_name,
                'Logic error: marked as "' || ua.working_status || '" but priority is ' || ua.priority_to_fix as description,
                'PRIORITY_LOGIC' as bug_category,
                datetime('now') as detected_at
            FROM components c
            JOIN component_usage_analysis ua ON c.component_id = ua.component_id
            WHERE ua.is_active = TRUE
              AND c.is_active = TRUE
              AND ((ua.working_status = 'Fully Working' AND ua.priority_to_fix IN ('HIGH', 'CRITICAL'))
                   OR (ua.working_status IN ('Broken', 'Missing') AND ua.priority_to_fix = 'LOW'))

            UNION ALL

            -- Missing Critical Dependencies
            SELECT
                'MISSING_DEPENDENCY' as alert_type,
                'HIGH' as severity,
                c.component_name,
                'Critical component missing: ' || ua.missing_dependencies as description,
                'DEPENDENCY_MISSING' as bug_category,
                datetime('now') as detected_at
            FROM components c
            JOIN component_usage_analysis ua ON c.component_id = ua.component_id
            WHERE ua.is_active = TRUE
              AND c.is_active = TRUE
              AND ua.working_status = 'Broken'
              AND ua.missing_dependencies LIKE '%missing%'
              AND ua.priority_to_fix IN ('HIGH', 'CRITICAL')

            UNION ALL

            -- FIXED: Effort Hours Logic Issues (Enhanced) - EXCLUDE "Fully Working" components
            SELECT
                'EFFORT_LOGIC' as alert_type,
                'LOW' as severity,
                c.component_name,
                'Effort hours (' || COALESCE(c.effort_hours, 0) || 'h) seems inconsistent with complexity (' || ua.complexity_to_fix || ')' as description,
                'EFFORT_MISMATCH' as bug_category,
                datetime('now') as detected_at
            FROM components c
            JOIN component_usage_analysis ua ON c.component_id = ua.component_id
            JOIN statuses s ON c.status_id = s.status_id
            WHERE ua.is_active = TRUE
              AND c.is_active = TRUE
              AND s.status_name != 'Fully Working'  -- EXCLUDE "Fully Working" components
              AND ((ua.complexity_to_fix = 'Hard' AND COALESCE(c.effort_hours, 0) < 8)
                   OR (ua.complexity_to_fix = 'Easy' AND COALESCE(c.effort_hours, 0) > 16))

            UNION ALL

            -- Stale Components (not updated recently)
            SELECT
                'STALE_COMPONENT' as alert_type,
                'INFO' as severity,
                c.component_name,
                'Component not updated in over 30 days (last: ' || c.updated_at || ')' as description,
                'STALE_DATA' as bug_category,
                datetime('now') as detected_at
            FROM components c
            WHERE c.is_active = TRUE
              AND julianday('now') - julianday(c.updated_at) > 30
              AND c.component_name NOT LIKE '%Test%'

            UNION ALL

            -- Production Readiness Issues
            SELECT
                'PRODUCTION_ISSUE' as alert_type,
                'MEDIUM' as severity,
                c.component_name,
                'Production readiness concern: ' || ua.production_ready || ' but working_status is ' || ua.working_status as description,
                'PROD_READINESS' as bug_category,
                datetime('now') as detected_at
            FROM components c
            JOIN component_usage_analysis ua ON c.component_id = ua.component_id
            WHERE ua.is_active = TRUE
              AND c.is_active = TRUE
              AND ua.production_ready = 'Yes'
              AND ua.working_status != 'Fully Working'

            UNION ALL

            -- Documentation Issues
            SELECT
                'DOCUMENTATION_ISSUE' as alert_type,
                'LOW' as severity,
                c.component_name,
                'Critical component lacks proper documentation (' || ua.documentation_status || ')' as description,
                'DOC_MISSING' as bug_category,
                datetime('now') as detected_at
            FROM components c
            JOIN component_usage_analysis ua ON c.component_id = ua.component_id
            WHERE ua.is_active = TRUE
              AND c.is_active = TRUE
              AND ua.priority_to_fix IN ('HIGH', 'CRITICAL')
              AND ua.documentation_status IN ('None', 'Limited', 'Basic')
              AND ua.working_status = 'Fully Working';
    """
    
    return update_view_sql

def main():
    """Main execution function."""
    print("🔧 Fixing Effort Logic Validation Rule")
    print("=" * 50)
    
    # Connect to database
    conn = connect_database()
    
    try:
        # Check current EFFORT_LOGIC alerts before fix
        print("🔍 Checking current EFFORT_LOGIC alerts...")
        cursor = conn.execute("""
            SELECT COUNT(*) as count 
            FROM bug_detection_report 
            WHERE alert_type = 'EFFORT_LOGIC'
        """)
        before_count = cursor.fetchone()[0]
        print(f"   Found {before_count} EFFORT_LOGIC alerts before fix")
        
        if before_count > 0:
            cursor = conn.execute("""
                SELECT component_name, description 
                FROM bug_detection_report 
                WHERE alert_type = 'EFFORT_LOGIC'
                LIMIT 5
            """)
            alerts = cursor.fetchall()
            print("   Sample alerts:")
            for alert in alerts:
                print(f"     • {alert['component_name']}: {alert['description']}")
        
        # Apply the fix
        print("\n📝 Updating bug_detection_report view to exclude 'Fully Working' components from EFFORT_LOGIC...")
        
        update_sql = fix_effort_logic_validation()
        conn.executescript(update_sql)
        
        print("✅ Successfully updated bug_detection_report view")
        
        # Check EFFORT_LOGIC alerts after fix
        print("\n🔍 Checking EFFORT_LOGIC alerts after fix...")
        cursor = conn.execute("""
            SELECT COUNT(*) as count 
            FROM bug_detection_report 
            WHERE alert_type = 'EFFORT_LOGIC'
        """)
        after_count = cursor.fetchone()[0]
        print(f"   Found {after_count} EFFORT_LOGIC alerts after fix")
        
        if after_count > 0:
            cursor = conn.execute("""
                SELECT component_name, description 
                FROM bug_detection_report 
                WHERE alert_type = 'EFFORT_LOGIC'
                ORDER BY component_name
            """)
            remaining_alerts = cursor.fetchall()
            print("   Remaining alerts (non-'Fully Working' components):")
            for alert in remaining_alerts:
                print(f"     • {alert['component_name']}: {alert['description']}")
        
        # Summary
        fixed_count = before_count - after_count
        print(f"\n📊 Summary:")
        print(f"   • EFFORT_LOGIC alerts before fix: {before_count}")
        print(f"   • EFFORT_LOGIC alerts after fix: {after_count}")
        print(f"   • Alerts resolved by excluding 'Fully Working': {fixed_count}")
        print(f"   • Bug detection system fixed successfully ✅")
        
        print("\n💡 Rule change applied:")
        print("   • EFFORT_LOGIC validation now excludes 'Fully Working' components")
        print("   • Completed components can have 0 effort hours regardless of complexity")
        print("   • Only incomplete components are checked for effort/complexity mismatch")
        
    except sqlite3.Error as e:
        print(f"❌ SQL execution failed: {e}")
        return 1
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return 1
    finally:
        conn.close()
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
