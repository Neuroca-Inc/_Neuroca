#!/usr/bin/env python3
"""
Add Broken Component Validation Rule
===================================

This script adds a validation rule to flag all components with "Broken" status
as critical issues in the bug detection report.

Usage:
    python scripts/sql/add_broken_component_validation.py
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

def add_broken_component_validation():
    """Add validation rule for broken components."""
    
    # SQL to drop and recreate the bug_detection_report view with broken component validation
    update_view_sql = """
    DROP VIEW IF EXISTS bug_detection_report;
    
    CREATE VIEW bug_detection_report AS
            -- CRITICAL: Broken Components (should always be flagged)
            SELECT
                'BROKEN_COMPONENT' as alert_type,
                'CRITICAL' as severity,
                c.component_name,
                'Component marked as BROKEN - requires immediate attention. Priority: ' || c.priority || ', Effort: ' || c.effort_hours || 'h' as description,
                'BROKEN_STATUS' as bug_category,
                datetime('now') as detected_at
            FROM components c
            JOIN statuses s ON c.status_id = s.status_id
            WHERE c.is_active = TRUE
              AND s.status_name = 'Broken'

            UNION ALL

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

            -- Effort Hours Logic Issues (Enhanced) - EXCLUDE "Fully Working" components
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
              AND s.status_name != 'Fully Working'  -- Exclude "Fully Working" components
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
    print("🔧 Adding Broken Component Validation Rule")
    print("=" * 50)
    
    # Connect to database
    conn = connect_database()
    
    try:
        # Check current broken components
        print("🔍 Checking for broken components...")
        cursor = conn.execute("""
            SELECT c.component_name, s.status_name, c.priority, c.effort_hours
            FROM components c
            JOIN statuses s ON c.status_id = s.status_id
            WHERE c.is_active = TRUE AND s.status_name = 'Broken'
        """)
        broken_components = cursor.fetchall()
        
        if broken_components:
            print(f"   Found {len(broken_components)} broken components:")
            for comp in broken_components:
                print(f"     • {comp['component_name']} (Priority: {comp['priority']}, Effort: {comp['effort_hours']}h)")
        else:
            print("   No broken components found")
        
        # Check if broken components are in bug report before fix
        cursor = conn.execute("""
            SELECT COUNT(*) as count 
            FROM bug_detection_report 
            WHERE alert_type = 'BROKEN_COMPONENT'
        """)
        before_count = cursor.fetchone()[0]
        print(f"   BROKEN_COMPONENT alerts before fix: {before_count}")
        
        # Apply the fix
        print("\n📝 Adding BROKEN_COMPONENT validation rule...")
        
        update_sql = add_broken_component_validation()
        conn.executescript(update_sql)
        
        print("✅ Successfully updated bug_detection_report view")
        
        # Check broken component alerts after fix
        print("\n🔍 Checking BROKEN_COMPONENT alerts after fix...")
        cursor = conn.execute("""
            SELECT COUNT(*) as count 
            FROM bug_detection_report 
            WHERE alert_type = 'BROKEN_COMPONENT'
        """)
        after_count = cursor.fetchone()[0]
        print(f"   BROKEN_COMPONENT alerts after fix: {after_count}")
        
        if after_count > 0:
            cursor = conn.execute("""
                SELECT component_name, description 
                FROM bug_detection_report 
                WHERE alert_type = 'BROKEN_COMPONENT'
                ORDER BY component_name
            """)
            alerts = cursor.fetchall()
            print("   Broken component alerts:")
            for alert in alerts:
                print(f"     • {alert['component_name']}: {alert['description']}")
        
        # Check total bug count
        cursor = conn.execute("SELECT COUNT(*) as total FROM bug_detection_report")
        total_bugs = cursor.fetchone()[0]
        print(f"\n📊 Total bugs in system: {total_bugs}")
        
        # Summary
        print(f"\n📊 Summary:")
        print(f"   • Broken components found: {len(broken_components)}")
        print(f"   • BROKEN_COMPONENT alerts before: {before_count}")
        print(f"   • BROKEN_COMPONENT alerts after: {after_count}")
        print(f"   • Total system bugs: {total_bugs}")
        
        if len(broken_components) > 0 and after_count == len(broken_components):
            print(f"   • ✅ All broken components now properly flagged in bug report")
        elif len(broken_components) > 0:
            print(f"   • ⚠️  Some broken components may not be flagged - investigate further")
        
        print("\n💡 Validation rule added:")
        print("   • All components with 'Broken' status now flagged as CRITICAL alerts")
        print("   • Broken components appear in bug detection report with detailed information")
        print("   • Alert includes priority and effort hours for triage")
        
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
