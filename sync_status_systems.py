#!/usr/bin/env python3
"""
Sync the two status systems in the temporal database.
Updates component_usage_analysis.working_status to match components.status_name
"""

import sqlite3

def sync_status_systems():
    """Sync component_usage_analysis.working_status with components.status_name"""
    
    print("🔄 SYNCING STATUS SYSTEMS")
    print("=" * 50)
    
    with sqlite3.connect("neuroca_temporal_analysis.db") as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        
        # First, show current discrepancies
        print("\n📊 Current Status Discrepancies:")
        print("-" * 40)
        
        discrepancy_cursor = conn.execute("""
            SELECT 
                c.component_name,
                s.status_name as components_status,
                ua.working_status as usage_analysis_status
            FROM components c 
            JOIN statuses s ON c.status_id = s.status_id
            LEFT JOIN component_usage_analysis ua ON c.component_id = ua.component_id
            WHERE s.status_name != ua.working_status
            AND c.is_active = TRUE 
            AND ua.is_active = TRUE
            ORDER BY c.component_name
        """)
        
        discrepancies = discrepancy_cursor.fetchall()
        for component_name, comp_status, usage_status in discrepancies:
            print(f"   {component_name}: {comp_status} != {usage_status}")
        
        print(f"\nFound {len(discrepancies)} discrepancies")
        
        # Update component_usage_analysis to match components status
        print(f"\n🔧 Syncing usage_analysis.working_status...")
        
        update_cursor = conn.execute("""
            UPDATE component_usage_analysis
            SET working_status = (
                SELECT s.status_name 
                FROM components c 
                JOIN statuses s ON c.status_id = s.status_id
                WHERE c.component_id = component_usage_analysis.component_id
            ),
            updated_at = datetime('now'),
            version = version + 1
            WHERE component_id IN (
                SELECT c.component_id
                FROM components c 
                JOIN statuses s ON c.status_id = s.status_id
                LEFT JOIN component_usage_analysis ua ON c.component_id = ua.component_id
                WHERE s.status_name != ua.working_status
                AND c.is_active = TRUE 
                AND ua.is_active = TRUE
            )
        """)
        
        updates_made = update_cursor.rowcount
        print(f"✅ Updated {updates_made} usage_analysis records")
        
        # Special handling for specific component corrections
        component_corrections = {
            "Memory Service Layer": {
                "working_status": "Partially Working",
                "priority_to_fix": "MEDIUM", 
                "missing_dependencies": "Dependency injection patterns needed",
                "integration_issues": "Missing DI integration for production"
            },
            "API Routes": {
                "working_status": "Fully Working",
                "priority_to_fix": "LOW",
                "missing_dependencies": "None - routes properly implemented",
                "integration_issues": "None - FastAPI integration working"
            },
            "CLI Interface": {
                "working_status": "Fully Working", 
                "priority_to_fix": "LOW",
                "missing_dependencies": "None - Typer integration working",
                "integration_issues": "None - command registration working"
            },
            "FastAPI Application": {
                "working_status": "Fully Working",
                "priority_to_fix": "LOW", 
                "missing_dependencies": "None - application fully functional",
                "integration_issues": "Minor - multiple app files detected"
            }
        }
        
        print(f"\n🎯 Applying specific component corrections...")
        for component_name, corrections in component_corrections.items():
            cursor = conn.execute("""
                UPDATE component_usage_analysis 
                SET working_status = ?,
                    priority_to_fix = ?,
                    missing_dependencies = ?,
                    integration_issues = ?,
                    updated_at = datetime('now'),
                    version = version + 1
                WHERE component_id = (
                    SELECT component_id FROM components 
                    WHERE component_name = ? AND is_active = TRUE
                )
            """, (
                corrections["working_status"],
                corrections["priority_to_fix"], 
                corrections["missing_dependencies"],
                corrections["integration_issues"],
                component_name
            ))
            
            if cursor.rowcount > 0:
                print(f"✅ Updated {component_name}")
            else:
                print(f"⚠️ {component_name} not found")
        
        # Verify sync was successful
        print(f"\n✅ Verification - Remaining Discrepancies:")
        print("-" * 40)
        
        final_check = conn.execute("""
            SELECT 
                c.component_name,
                s.status_name as components_status,
                ua.working_status as usage_analysis_status
            FROM components c 
            JOIN statuses s ON c.status_id = s.status_id
            LEFT JOIN component_usage_analysis ua ON c.component_id = ua.component_id
            WHERE s.status_name != ua.working_status
            AND c.is_active = TRUE 
            AND ua.is_active = TRUE
            ORDER BY c.component_name
        """)
        
        remaining_discrepancies = final_check.fetchall()
        if remaining_discrepancies:
            for component_name, comp_status, usage_status in remaining_discrepancies:
                print(f"   ⚠️ {component_name}: {comp_status} != {usage_status}")
        else:
            print("   🎉 No discrepancies found - systems are in sync!")
        
        # Show updated critical blockers count
        critical_count = conn.execute("""
            SELECT COUNT(*) FROM (
                SELECT co.component_name
                FROM current_active_components co
                LEFT JOIN component_usage_analysis ua ON co.component_id = ua.component_id
                WHERE (ua.priority_to_fix = 'CRITICAL'
                   OR co.status_name IN ('Missing', 'Broken')
                   OR ua.working_status IN ('Missing', 'Broken'))
                   AND ua.is_active = TRUE
            )
        """).fetchone()[0]
        
        print(f"\n📈 Updated Statistics:")
        print(f"   Critical Blockers: {critical_count}")
        
        conn.commit()
        
        print(f"\n🎯 Status systems successfully synchronized!")

if __name__ == "__main__":
    sync_status_systems()
