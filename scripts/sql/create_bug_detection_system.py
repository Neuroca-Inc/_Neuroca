#!/usr/bin/env python3
"""
Create an intelligent bug detection system that automatically identifies
potential issues by analyzing data patterns across tables.
"""

import sqlite3

def create_bug_detection_system():
    """Create comprehensive bug detection views and tables."""
    
    print("🔍 CREATING BUG DETECTION SYSTEM")
    print("=" * 50)
    
    with sqlite3.connect("neuroca_temporal_analysis.db") as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        
        # 1. Create bug_alerts table for tracking detected issues
        print("📊 Creating bug_alerts table...")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS bug_alerts (
                alert_id INTEGER PRIMARY KEY AUTOINCREMENT,
                alert_type TEXT NOT NULL,
                severity TEXT NOT NULL CHECK (severity IN ('CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO')),
                component_name TEXT,
                description TEXT NOT NULL,
                detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                resolved_at TIMESTAMP NULL,
                is_active BOOLEAN DEFAULT TRUE,
                auto_generated BOOLEAN DEFAULT TRUE,
                raw_data TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 2. Create comprehensive bug detection view
        print("🔍 Creating bug_detection_report view...")
        conn.execute("DROP VIEW IF EXISTS bug_detection_report")
        conn.execute("""
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
            
            -- Effort Hours Logic Issues
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
              AND ua.working_status = 'Fully Working'
        """)
        
        # 3. Create temporal analysis for component stability
        print("📈 Creating component_stability_analysis view...")
        conn.execute("DROP VIEW IF EXISTS component_stability_analysis")
        conn.execute("""
            CREATE VIEW component_stability_analysis AS
            SELECT 
                c.component_name,
                COUNT(DISTINCT ch.history_timestamp) as change_count,
                COUNT(DISTINCT DATE(ch.history_timestamp)) as days_with_changes,
                MIN(ch.history_timestamp) as first_change,
                MAX(ch.history_timestamp) as last_change,
                MAX(ch.version) as current_version,
                CASE 
                    WHEN COUNT(DISTINCT ch.history_timestamp) > 10 THEN 'UNSTABLE'
                    WHEN COUNT(DISTINCT ch.history_timestamp) > 5 THEN 'MODERATE'
                    ELSE 'STABLE'
                END as stability_rating,
                CASE 
                    WHEN COUNT(DISTINCT DATE(ch.history_timestamp)) > 5 THEN 'HIGH_ACTIVITY'
                    WHEN COUNT(DISTINCT DATE(ch.history_timestamp)) > 2 THEN 'MEDIUM_ACTIVITY'
                    ELSE 'LOW_ACTIVITY'
                END as activity_level
            FROM components c
            LEFT JOIN component_change_history ch ON c.component_name = ch.component_name
            WHERE c.is_active = TRUE
            GROUP BY c.component_name
            ORDER BY change_count DESC
        """)
        
        # 4. Create priority dashboard view
        print("🎯 Creating priority_dashboard view...")
        conn.execute("DROP VIEW IF EXISTS priority_dashboard")
        conn.execute("""
            CREATE VIEW priority_dashboard AS
            SELECT 
                'IMMEDIATE_ACTION' as urgency_level,
                COUNT(*) as component_count,
                GROUP_CONCAT(c.component_name, ', ') as components
            FROM components c
            JOIN component_usage_analysis ua ON c.component_id = ua.component_id
            WHERE ua.is_active = TRUE 
              AND c.is_active = TRUE
              AND ua.working_status IN ('Broken', 'Missing')
              AND ua.priority_to_fix IN ('HIGH', 'CRITICAL')
            
            UNION ALL
            
            SELECT 
                'NEXT_SPRINT' as urgency_level,
                COUNT(*) as component_count,
                GROUP_CONCAT(c.component_name, ', ') as components
            FROM components c
            JOIN component_usage_analysis ua ON c.component_id = ua.component_id
            WHERE ua.is_active = TRUE 
              AND c.is_active = TRUE
              AND ua.working_status IN ('Partially Working', 'Exists But Not Connected')
              AND ua.priority_to_fix = 'MEDIUM'
            
            UNION ALL
            
            SELECT 
                'TECHNICAL_DEBT' as urgency_level,
                COUNT(*) as component_count,
                GROUP_CONCAT(c.component_name, ', ') as components
            FROM components c
            JOIN component_usage_analysis ua ON c.component_id = ua.component_id
            WHERE ua.is_active = TRUE 
              AND c.is_active = TRUE
              AND ua.working_status = 'Duplicated/Confused'
              OR (ua.production_ready = 'No' AND ua.working_status = 'Fully Working')
            
            UNION ALL
            
            SELECT 
                'WORKING_WELL' as urgency_level,
                COUNT(*) as component_count,
                'Components functioning properly' as components
            FROM components c
            JOIN component_usage_analysis ua ON c.component_id = ua.component_id
            WHERE ua.is_active = TRUE 
              AND c.is_active = TRUE
              AND ua.working_status = 'Fully Working'
              AND ua.priority_to_fix = 'LOW'
              AND ua.production_ready = 'Yes'
        """)
        
        # 5. Create automated bug alert population function
        print("🤖 Creating automated bug detection trigger...")
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS auto_detect_bugs
            AFTER UPDATE ON component_usage_analysis
            FOR EACH ROW
            WHEN NEW.updated_at != OLD.updated_at
            BEGIN
                -- Clear old alerts for this component
                UPDATE bug_alerts 
                SET is_active = FALSE, resolved_at = datetime('now')
                WHERE component_name = (SELECT component_name FROM components WHERE component_id = NEW.component_id)
                  AND is_active = TRUE
                  AND auto_generated = TRUE;
                
                -- Insert new critical alerts for broken components
                INSERT INTO bug_alerts (alert_type, severity, component_name, description, raw_data)
                SELECT 
                    'CRITICAL_COMPONENT_BROKEN',
                    'CRITICAL',
                    c.component_name,
                    'Component status changed to BROKEN - requires immediate attention',
                    'working_status: ' || NEW.working_status || ', priority: ' || NEW.priority_to_fix
                FROM components c
                WHERE c.component_id = NEW.component_id
                  AND NEW.working_status = 'Broken'
                  AND NEW.priority_to_fix IN ('HIGH', 'CRITICAL');
            END
        """)
        
        # 6. Populate initial bug alerts
        print("🚨 Populating initial bug alerts...")
        conn.execute("""
            INSERT INTO bug_alerts (alert_type, severity, component_name, description, raw_data)
            SELECT 
                bug_category,
                severity,
                component_name,
                description,
                'auto-detected on: ' || detected_at
            FROM bug_detection_report
            WHERE severity IN ('CRITICAL', 'HIGH')
        """)
        
        conn.commit()
        
        # 7. Test the system
        print("\n✅ TESTING BUG DETECTION SYSTEM:")
        print("-" * 40)
        
        # Show detected bugs
        bugs = conn.execute("""
            SELECT alert_type, severity, component_name, description 
            FROM bug_alerts 
            WHERE is_active = TRUE 
            ORDER BY 
                CASE severity 
                    WHEN 'CRITICAL' THEN 1 
                    WHEN 'HIGH' THEN 2 
                    WHEN 'MEDIUM' THEN 3 
                    ELSE 4 
                END
            LIMIT 10
        """).fetchall()
        
        if bugs:
            print(f"🔍 Detected {len(bugs)} potential issues:")
            for alert_type, severity, component_name, description in bugs:
                print(f"   [{severity}] {component_name}: {description}")
        else:
            print("✅ No critical bugs detected - system is healthy!")
        
        # Show priority dashboard
        print(f"\n🎯 PRIORITY DASHBOARD:")
        print("-" * 25)
        dashboard = conn.execute("SELECT * FROM priority_dashboard").fetchall()
        for urgency, count, components in dashboard:
            if count > 0:
                print(f"   {urgency}: {count} components")
                if count <= 5:  # Show names if not too many
                    print(f"      → {components[:100]}{'...' if len(components) > 100 else ''}")
        
        # Show stability analysis
        print(f"\n📊 COMPONENT STABILITY:")
        print("-" * 25)
        stability = conn.execute("""
            SELECT component_name, stability_rating, change_count, activity_level
            FROM component_stability_analysis 
            WHERE stability_rating != 'STABLE' OR activity_level = 'HIGH_ACTIVITY'
            ORDER BY change_count DESC
            LIMIT 5
        """).fetchall()
        
        if stability:
            for name, rating, changes, activity in stability:
                print(f"   {name}: {rating} ({changes} changes, {activity})")
        else:
            print("   All components are stable")
        
        print(f"\n🎉 BUG DETECTION SYSTEM CREATED!")
        print("   📊 Views: bug_detection_report, component_stability_analysis, priority_dashboard")
        print("   🚨 Table: bug_alerts (with auto-population)")
        print("   🤖 Trigger: auto_detect_bugs (monitors changes)")

if __name__ == "__main__":
    create_bug_detection_system()
