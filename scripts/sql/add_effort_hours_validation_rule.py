#!/usr/bin/env python3
"""
Add Effort Hours Validation Rule to Bug Detection System
=======================================================

This script adds a new validation rule to detect components marked as "Fully Working" 
but still having effort_hours > 0, which represents a logical inconsistency.

Usage:
    python scripts/sql/add_effort_hours_validation_rule.py
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

def add_effort_hours_validation():
    """Add the effort hours validation rule to bug detection system."""
    
    # SQL to drop and recreate the bug_detection_report view with new validation
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

            -- NEW: Effort Hours Logic Inconsistency
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

            -- Effort Hours Logic Issues (Enhanced)
            SELECT
                'EFFORT_LOGIC' as alert_type,
                'LOW' as severity,
                c.component_name,
                'Effort hours (' || COALESCE(c.effort_hours, 0) || 'h) seems inconsistent with complexity (' || ua.complexity_to_fix || ')' as description,
                'EFFORT_MISMATCH' as bug_category,
                datetime('now') as detected_at
            FROM components c
            JOIN component_usage_analysis ua ON c.component_id = ua.component_id
            WHERE ua.is_active = TRUE
              AND c.is_active = TRUE
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

def create_effort_hours_fix_script():
    """Create a script to automatically fix the effort hours inconsistency."""
    
    fix_script_sql = """
    -- Script to fix effort hours inconsistency
    -- Sets effort_hours to 0 for all components marked as "Fully Working"
    
    BEGIN TRANSACTION;
    
    -- Create a backup log of changes before making them
    CREATE TEMP TABLE effort_hours_fixes AS
    SELECT 
        c.component_id,
        c.component_name,
        s.status_name,
        c.effort_hours as old_effort_hours,
        0 as new_effort_hours,
        datetime('now') as fix_timestamp
    FROM components c
    JOIN statuses s ON c.status_id = s.status_id
    WHERE c.is_active = TRUE
      AND s.status_name = 'Fully Working' 
      AND c.effort_hours > 0;
    
    -- Show what will be changed
    SELECT 'Components to fix:' as action, COUNT(*) as count FROM effort_hours_fixes;
    SELECT component_name, old_effort_hours FROM effort_hours_fixes ORDER BY old_effort_hours DESC;
    
    -- Apply the fix (commented out for safety - uncomment to execute)
    /*
    UPDATE components 
    SET effort_hours = 0,
        updated_at = datetime('now'),
        notes = CASE 
            WHEN notes IS NULL OR notes = '' THEN 'Auto-fixed: Set effort_hours to 0 for Fully Working component'
            ELSE notes || ' | Auto-fixed: Set effort_hours to 0 for Fully Working component'
        END
    WHERE component_id IN (SELECT component_id FROM effort_hours_fixes);
    */
    
    -- Log the fixes for audit trail
    INSERT INTO component_issues (component_id, issue_description, severity, resolved, created_by, resolved_by)
    SELECT 
        component_id,
        'Auto-fix applied: effort_hours set to 0 for Fully Working component (was ' || old_effort_hours || 'h)',
        'INFO',
        TRUE,
        'automated_fix_script',
        'automated_fix_script'
    FROM effort_hours_fixes;
    
    COMMIT;
    """
    
    return fix_script_sql

def main():
    """Main execution function."""
    print("🔧 Adding Effort Hours Validation Rule to Bug Detection System")
    print("=" * 70)
    
    # Connect to database
    conn = connect_database()
    
    try:
        # Add the new validation rule
        print("📝 Updating bug_detection_report view with effort hours validation...")
        
        update_sql = add_effort_hours_validation()
        conn.executescript(update_sql)
        
        print("✅ Successfully updated bug_detection_report view")
        
        # Test the new rule
        print("\n🔍 Testing new validation rule...")
        cursor = conn.execute("""
            SELECT alert_type, severity, component_name, description 
            FROM bug_detection_report 
            WHERE alert_type = 'EFFORT_HOURS_INCONSISTENCY'
            ORDER BY component_name
        """)
        
        effort_bugs = cursor.fetchall()
        print(f"✅ Found {len(effort_bugs)} components with effort hours inconsistency")
        
        if effort_bugs:
            print("\n📋 Components flagged:")
            for bug in effort_bugs[:5]:  # Show first 5
                print(f"   • {bug['component_name']}: {bug['description']}")
            if len(effort_bugs) > 5:
                print(f"   ... and {len(effort_bugs) - 5} more")
        
        # Create the fix script
        print("\n💾 Creating effort hours fix script...")
        fix_script_path = Path("scripts/sql/fix_effort_hours_inconsistency.sql")
        fix_script_content = create_effort_hours_fix_script()
        
        with open(fix_script_path, 'w') as f:
            f.write(fix_script_content)
        
        print(f"✅ Created fix script: {fix_script_path}")
        
        # Summary
        print("\n📊 Summary:")
        print(f"   • Added EFFORT_HOURS_INCONSISTENCY validation rule")
        print(f"   • Detected {len(effort_bugs)} inconsistent components")
        print(f"   • Created automated fix script")
        print(f"   • Bug detection system updated successfully")
        
        print("\n💡 Next steps:")
        print("   1. Review the validation report in reports/")
        print("   2. Run the fix script if you want to auto-correct the data")
        print("   3. Monitor the bug_detection_report view for ongoing issues")
        
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
