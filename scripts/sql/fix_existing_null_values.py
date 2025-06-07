#!/usr/bin/env python3
"""
Fix existing NULL values in component_usage_analysis table.
Updates existing records that have missing priority_to_fix and other fields.
"""

import sqlite3

def fix_existing_null_values():
    """Fix NULL values in existing component_usage_analysis records."""
    
    print("🔧 FIXING EXISTING NULL VALUES")
    print("=" * 50)
    
    with sqlite3.connect("neuroca_temporal_analysis.db") as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        
        # Get records with NULL values
        null_records = conn.execute("""
            SELECT 
                ua.analysis_id,
                ua.component_id,
                c.component_name,
                ua.working_status,
                ua.priority_to_fix,
                ua.current_file_paths,
                s.status_name
            FROM component_usage_analysis ua
            JOIN components c ON ua.component_id = c.component_id
            JOIN statuses s ON c.status_id = s.status_id
            WHERE ua.priority_to_fix IS NULL 
               OR ua.current_file_paths IS NULL 
               OR ua.current_file_paths = ''
            AND ua.is_active = TRUE
            ORDER BY c.component_name
        """).fetchall()
        
        print(f"📊 Found {len(null_records)} records with NULL values:")
        for analysis_id, _, name, working_status, priority, file_path, status_name in null_records:
            print(f"   - {name} (working_status: {working_status}, priority: {priority})")
        
        # Fix each record
        print(f"\n🔧 Fixing NULL values...")
        
        for analysis_id, component_id, component_name, working_status, priority_to_fix, current_file_paths, status_name in null_records:
            
            # Determine priority_to_fix if NULL
            if not priority_to_fix:
                if working_status == "Broken":
                    priority_to_fix = "HIGH"
                elif working_status == "Missing":
                    priority_to_fix = "HIGH"
                elif working_status == "Partially Working":
                    priority_to_fix = "MEDIUM"
                elif working_status == "Exists But Not Connected":
                    priority_to_fix = "MEDIUM"
                elif working_status == "Duplicated/Confused":
                    priority_to_fix = "MEDIUM"
                elif working_status == "Blocked by missing service layer":
                    priority_to_fix = "HIGH"
                else:  # Fully Working
                    priority_to_fix = "LOW"
            
            # Get current_file_paths from components table if missing
            if not current_file_paths or current_file_paths == '':
                file_path_result = conn.execute("""
                    SELECT file_path FROM components WHERE component_id = ?
                """, (component_id,)).fetchone()
                
                if file_path_result and file_path_result[0]:
                    current_file_paths = file_path_result[0]
                else:
                    current_file_paths = "N/A"
            
            # Determine complexity_to_fix if needed
            if "API" in component_name or "FastAPI" in component_name:
                complexity_to_fix = "Medium"
            elif "Memory" in component_name:
                complexity_to_fix = "Hard"
            elif "CLI" in component_name:
                complexity_to_fix = "Medium"
            elif working_status == "Broken":
                complexity_to_fix = "Hard"
            elif working_status == "Missing":
                complexity_to_fix = "Medium"
            else:
                complexity_to_fix = "Easy"
            
            # Determine missing_dependencies
            if working_status == "Fully Working":
                missing_dependencies = "None - component working properly"
            elif working_status == "Broken":
                missing_dependencies = "Investigation needed - component broken"
            elif working_status == "Missing":
                missing_dependencies = "Complete implementation required"
            elif working_status == "Exists But Not Connected":
                missing_dependencies = "Integration wiring needed"
            elif working_status == "Duplicated/Confused":
                missing_dependencies = "Consolidation needed"
            elif working_status == "Partially Working":
                missing_dependencies = "Completion needed"
            else:
                missing_dependencies = "Analysis needed"
            
            # Determine integration_issues
            if working_status == "Fully Working":
                integration_issues = "None - properly integrated"
            elif "API" in component_name:
                integration_issues = "Service layer integration needed"
            elif "Memory" in component_name:
                integration_issues = "Backend wiring needed"
            elif "CLI" in component_name:
                integration_issues = "Command registration needed"
            else:
                integration_issues = "Integration analysis needed"
            
            # Determine additional fields
            if working_status == "Fully Working":
                expected_usage = "Direct integration and usage"
                actual_integration_status = "Fully integrated"
                production_ready = "Yes"
                documentation_status = "Good"
                testing_status = "Good"
            elif working_status == "Exists But Not Connected":
                expected_usage = "Needs integration wiring"
                actual_integration_status = "Not connected"
                production_ready = "No"
                documentation_status = "Limited"
                testing_status = "Limited"
            elif working_status == "Broken":
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
            
            # Update the record
            cursor = conn.execute("""
                UPDATE component_usage_analysis 
                SET 
                    expected_usage = COALESCE(expected_usage, ?),
                    actual_integration_status = COALESCE(actual_integration_status, ?),
                    missing_dependencies = COALESCE(missing_dependencies, ?),
                    integration_issues = COALESCE(integration_issues, ?),
                    priority_to_fix = COALESCE(priority_to_fix, ?),
                    complexity_to_fix = COALESCE(complexity_to_fix, ?),
                    current_file_paths = COALESCE(NULLIF(current_file_paths, ''), ?),
                    production_ready = COALESCE(production_ready, ?),
                    documentation_status = COALESCE(documentation_status, ?),
                    testing_status = COALESCE(testing_status, ?),
                    updated_at = datetime('now'),
                    version = version + 1
                WHERE analysis_id = ?
            """, (
                expected_usage,
                actual_integration_status,
                missing_dependencies,
                integration_issues,
                priority_to_fix,
                complexity_to_fix,
                current_file_paths,
                production_ready,
                documentation_status,
                testing_status,
                analysis_id
            ))
            
            if cursor.rowcount > 0:
                print(f"✅ Fixed NULL values for: {component_name}")
            else:
                print(f"⚠️ Failed to fix: {component_name}")
        
        # Verify the fix
        print(f"\n✅ Verification:")
        print("-" * 30)
        
        remaining_nulls = conn.execute("""
            SELECT 
                COUNT(*) as total_records,
                SUM(CASE WHEN priority_to_fix IS NULL THEN 1 ELSE 0 END) as missing_priority,
                SUM(CASE WHEN working_status IS NULL THEN 1 ELSE 0 END) as missing_working_status,
                SUM(CASE WHEN current_file_paths IS NULL OR current_file_paths = '' THEN 1 ELSE 0 END) as missing_file_path
            FROM component_usage_analysis 
            WHERE is_active = TRUE
        """).fetchone()
        
        total_records, missing_priority, missing_working_status, missing_file_path = remaining_nulls
        
        print(f"   Total Usage Analysis Records: {total_records}")
        print(f"   Missing Priority: {missing_priority}")
        print(f"   Missing Working Status: {missing_working_status}")
        print(f"   Missing File Paths: {missing_file_path}")
        
        if missing_priority == 0 and missing_file_path == 0:
            print(f"   🎉 All NULL values fixed!")
        else:
            print(f"   ⚠️ Still have NULL values to fix")
        
        conn.commit()
        print(f"\n🎯 NULL value fixes completed!")

if __name__ == "__main__":
    fix_existing_null_values()
