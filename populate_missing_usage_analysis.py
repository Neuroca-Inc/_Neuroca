#!/usr/bin/env python3
"""
Populate missing component_usage_analysis records.
Creates usage analysis for components that don't have it.
"""

import sqlite3

def populate_missing_usage_analysis():
    """Create usage analysis records for components that don't have them."""
    
    print("🔧 POPULATING MISSING USAGE ANALYSIS")
    print("=" * 50)
    
    with sqlite3.connect("neuroca_temporal_analysis.db") as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        
        # Get components missing usage analysis
        missing_components = conn.execute("""
            SELECT 
                c.component_id,
                c.component_name,
                c.file_path,
                s.status_name,
                c.effort_hours,
                c.priority
            FROM components c 
            LEFT JOIN component_usage_analysis ua ON c.component_id = ua.component_id
            JOIN statuses s ON c.status_id = s.status_id
            WHERE c.is_active = TRUE AND ua.component_id IS NULL
            ORDER BY c.component_name
        """).fetchall()
        
        print(f"📊 Found {len(missing_components)} components without usage analysis:")
        for _, name, file_path, status, effort, priority in missing_components:
            print(f"   - {name} ({status})")
        
        # Create default usage analysis records
        print(f"\n🔧 Creating usage analysis records...")
        
        for component_id, component_name, file_path, status_name, effort_hours, priority in missing_components:
            
            # Determine working_status (map to allowed constraint values)
            if status_name == "Duplicated":
                working_status = "Duplicated/Confused"  # Map to allowed constraint value
            else:
                working_status = status_name
            
            # Determine priority_to_fix based on status
            if status_name == "Broken":
                priority_to_fix = "HIGH"
            elif status_name == "Missing":
                priority_to_fix = "HIGH"
            elif status_name == "Partially Working":
                priority_to_fix = "MEDIUM"
            elif status_name == "Exists But Not Connected":
                priority_to_fix = "MEDIUM"
            elif status_name == "Duplicated":
                priority_to_fix = "LOW"
            elif status_name == "Duplicated/Confused":
                priority_to_fix = "MEDIUM"
            elif status_name == "Blocked by missing service layer":
                priority_to_fix = "HIGH"
            else:  # Fully Working
                priority_to_fix = "LOW"
            
            # Determine complexity based on component type and status
            if "API" in component_name or "FastAPI" in component_name:
                complexity_to_fix = "Medium"
            elif "Memory" in component_name:
                complexity_to_fix = "Hard"
            elif "CLI" in component_name:
                complexity_to_fix = "Medium"
            elif status_name == "Broken":
                complexity_to_fix = "Hard"
            elif status_name == "Missing":
                complexity_to_fix = "Medium"
            else:
                complexity_to_fix = "Easy"
            
            # Determine missing_dependencies
            if status_name == "Fully Working":
                missing_dependencies = "None - component working properly"
            elif status_name == "Broken":
                missing_dependencies = "Investigation needed - component broken"
            elif status_name == "Missing":
                missing_dependencies = "Complete implementation required"
            elif status_name == "Exists But Not Connected":
                missing_dependencies = "Integration wiring needed"
            elif status_name == "Duplicated":
                missing_dependencies = "Consolidation needed"
            elif status_name == "Partially Working":
                missing_dependencies = "Completion needed"
            else:
                missing_dependencies = "Analysis needed"
            
            # Determine integration_issues
            if "Fully Working" in status_name:
                integration_issues = "None - properly integrated"
            elif "API" in component_name:
                integration_issues = "Service layer integration needed"
            elif "Memory" in component_name:
                integration_issues = "Backend wiring needed"
            elif "CLI" in component_name:
                integration_issues = "Command registration needed"
            else:
                integration_issues = "Integration analysis needed"
            
            # Get current file paths (handle multiple paths)
            current_file_paths = file_path if file_path else "N/A"
            
            # Determine additional fields based on status
            if status_name == "Fully Working":
                expected_usage = "Direct integration and usage"
                actual_integration_status = "Fully integrated"
                production_ready = "Yes"
                documentation_status = "Good"
                testing_status = "Good"
            elif status_name == "Exists But Not Connected":
                expected_usage = "Needs integration wiring"
                actual_integration_status = "Not connected"
                production_ready = "No"
                documentation_status = "Limited"
                testing_status = "Limited"
            elif status_name == "Broken":
                expected_usage = "Needs repair and integration"
                actual_integration_status = "Broken"
                production_ready = "No"
                documentation_status = "Basic"
                testing_status = "None"
            else:
                expected_usage = "Analysis needed"
                actual_integration_status = "Unknown"
                production_ready = "No"
                documentation_status = "Limited"
                testing_status = "Limited"
            
            # Insert usage analysis record
            cursor = conn.execute("""
                INSERT INTO component_usage_analysis (
                    component_id,
                    expected_usage,
                    actual_integration_status,
                    missing_dependencies,
                    integration_issues,
                    working_status,
                    priority_to_fix,
                    complexity_to_fix,
                    current_file_paths,
                    production_ready,
                    documentation_status,
                    testing_status,
                    created_at,
                    updated_at,
                    created_by,
                    is_active,
                    version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'), 'populate_script', TRUE, 1)
            """, (
                component_id,
                expected_usage,
                actual_integration_status,
                missing_dependencies,
                integration_issues,
                working_status,
                priority_to_fix,
                complexity_to_fix,
                current_file_paths,
                production_ready,
                documentation_status,
                testing_status
            ))
            
            if cursor.rowcount > 0:
                print(f"✅ Created usage analysis for: {component_name}")
            else:
                print(f"⚠️ Failed to create usage analysis for: {component_name}")
        
        # Verify completion
        print(f"\n✅ Verification:")
        print("-" * 30)
        
        final_stats = conn.execute("""
            SELECT 
                (SELECT COUNT(*) FROM components WHERE is_active = TRUE) as total_components,
                (SELECT COUNT(*) FROM component_usage_analysis WHERE is_active = TRUE) as total_usage_analysis,
                (SELECT COUNT(*) FROM components c 
                 LEFT JOIN component_usage_analysis ua ON c.component_id = ua.component_id 
                 WHERE c.is_active = TRUE AND ua.component_id IS NULL) as still_missing
        """).fetchone()
        
        total_components, total_usage_analysis, still_missing = final_stats
        
        print(f"   Total Components: {total_components}")
        print(f"   Total Usage Analysis: {total_usage_analysis}")
        print(f"   Still Missing: {still_missing}")
        
        if still_missing == 0:
            print(f"   🎉 All components now have usage analysis!")
        else:
            print(f"   ⚠️ {still_missing} components still missing usage analysis")
        
        # Check data quality
        data_quality = conn.execute("""
            SELECT 
                COUNT(*) as total_records,
                SUM(CASE WHEN priority_to_fix IS NULL THEN 1 ELSE 0 END) as missing_priority,
                SUM(CASE WHEN working_status IS NULL THEN 1 ELSE 0 END) as missing_working_status,
                SUM(CASE WHEN current_file_paths IS NULL OR current_file_paths = '' THEN 1 ELSE 0 END) as missing_file_path
            FROM component_usage_analysis 
            WHERE is_active = TRUE
        """).fetchone()
        
        total_records, missing_priority, missing_working_status, missing_file_path = data_quality
        
        print(f"\n📊 Updated Data Quality:")
        print(f"   Total Usage Analysis Records: {total_records}")
        print(f"   Missing Priority: {missing_priority}")
        print(f"   Missing Working Status: {missing_working_status}")
        print(f"   Missing File Paths: {missing_file_path}")
        
        # Show updated critical blockers
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
        
        print(f"\n📈 Updated Critical Blockers: {critical_count}")
        
        conn.commit()
        print(f"\n🎯 Usage analysis population completed!")

if __name__ == "__main__":
    populate_missing_usage_analysis()
