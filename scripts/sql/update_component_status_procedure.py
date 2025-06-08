#!/usr/bin/env python3
"""
Component Status Update Procedure

This script provides a controlled, stored-procedure-like interface for updating
component statuses in the neuroca_temporal_analysis database. It ensures data
integrity, proper logging, and maintains audit trails.

Usage:
    python update_component_status_procedure.py --component-name "API Error Handling" --status "Fully Working" --notes "Comprehensive API implementation completed"
"""

import argparse
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional


class ComponentStatusUpdater:
    """Controlled interface for updating component statuses."""
    
    def __init__(self, db_path: str = "neuroca_temporal_analysis.db"):
        self.db_path = db_path
        self.valid_statuses = {
            "Broken": 1,
            "Duplicated": 2,
            "Exists But Not Connected": 3,
            "Blocked by missing service layer": 4,
            "Duplicated/Confused": 5,
            "Missing": 6,
            "Partially Working": 7,
            "Fully Working": 8,
        }
        self.valid_priorities = ["Critical", "High", "Medium", "Low"]
    
    def validate_inputs(self, component_name: str, status: str, priority: Optional[str] = None) -> bool:
        """Validate input parameters."""
        if not component_name or len(component_name) < 3:
            print(f"Error: Component name must be at least 3 characters: '{component_name}'")
            return False
        
        if status not in self.valid_statuses:
            print(f"Error: Invalid status '{status}'. Valid options: {list(self.valid_statuses.keys())}")
            return False
        
        if priority and priority not in self.valid_priorities:
            print(f"Error: Invalid priority '{priority}'. Valid options: {self.valid_priorities}")
            return False
        
        return True
    
    def get_component_info(self, conn: sqlite3.Connection, component_name: str) -> Optional[dict]:
        """Get current component information from component_usage_analysis (master source)."""
        cursor = conn.cursor()
        cursor.execute("""
            SELECT cu.analysis_id, cu.component_id, c.component_name, cu.working_status,
                   cu.priority_to_fix, cu.complexity_to_fix, cu.current_file_paths, 
                   cu.integration_issues, cu.version, cu.updated_at
            FROM component_usage_analysis cu
            JOIN components c ON cu.component_id = c.component_id
            WHERE c.component_name = ? AND cu.is_active = TRUE
        """, (component_name,))
        
        row = cursor.fetchone()
        if row:
            return {
                "analysis_id": row[0],
                "component_id": row[1],
                "component_name": row[2],
                "working_status": row[3],
                "priority_to_fix": row[4],
                "complexity_to_fix": row[5],
                "current_file_paths": row[6],
                "integration_issues": row[7],
                "version": row[8],
                "updated_at": row[9],
            }
        return None
    
    def update_component_status(
        self,
        component_name: str,
        status: str,
        notes: Optional[str] = None,
        priority: Optional[str] = None,
        effort_hours: Optional[int] = None,
        updated_by: str = "api_implementation_update",
    ) -> bool:
        """
        Update component status with full audit trail.
        
        Args:
            component_name: Name of the component to update
            status: New status name
            notes: Additional notes (will be appended to existing)
            priority: New priority (optional)
            effort_hours: New effort hours (optional)
            updated_by: Who made the update
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.validate_inputs(component_name, status, priority):
            return False
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Enable foreign keys
                conn.execute("PRAGMA foreign_keys = ON")
                
                # Get current component info
                current_info = self.get_component_info(conn, component_name)
                if not current_info:
                    print(f"Error: Component '{component_name}' not found")
                    return False
                
                # Print current status
                print(f"Current status of '{component_name}': {current_info['working_status']}")
                
                # Check if this is actually a change
                if current_info["working_status"] == status:
                    print(f"Component '{component_name}' is already '{status}'. No update needed.")
                    return True
                
                # Prepare update fields for component_usage_analysis
                update_fields = []
                update_values = []
                
                # Always update working_status (this will trigger sync to components table)
                update_fields.append("working_status = ?")
                update_values.append(status)
                
                if priority:
                    update_fields.append("priority_to_fix = ?")
                    update_values.append(priority)
                
                # Handle notes in integration_issues field
                current_issues = current_info["integration_issues"] or ""
                if notes:
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    if current_issues:
                        new_issues = f"{current_issues} | Updated {timestamp}: {notes}"
                    else:
                        new_issues = f"Updated {timestamp}: {notes}"
                    
                    update_fields.append("integration_issues = ?")
                    update_values.append(new_issues)
                
                update_fields.append("updated_at = CURRENT_TIMESTAMP")
                update_fields.append("version = version + 1")
                update_fields.append("created_by = ?")
                update_values.append(updated_by)
                
                # Add analysis_id for WHERE clause
                update_values.append(current_info["analysis_id"])
                
                # Execute update on component_usage_analysis (triggers will sync to components)
                update_sql = f"""
                    UPDATE component_usage_analysis 
                    SET {', '.join(update_fields)}
                    WHERE analysis_id = ?
                """
                
                cursor = conn.cursor()
                cursor.execute(update_sql, update_values)
                
                if cursor.rowcount == 0:
                    print(f"Error: No rows updated for component '{component_name}'")
                    return False
                
                # Verify the update
                updated_info = self.get_component_info(conn, component_name)
                if updated_info and updated_info["working_status"] == status:
                    print(f"✅ Successfully updated '{component_name}' from '{current_info['working_status']}' to '{status}'")
                    print(f"   Triggers will automatically sync to components table")
                    if notes:
                        print(f"   Notes: {notes}")
                    return True
                else:
                    print(f"Error: Update verification failed for component '{component_name}'")
                    return False
                
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return False
        except Exception as e:
            print(f"Unexpected error: {e}")
            return False
    
    def batch_update_api_components(self) -> bool:
        """Update API-related components to Fully Working status."""
        api_updates = [
            {
                "component_name": "API Error Handling",
                "status": "Fully Working",
                "notes": "Comprehensive error handling implemented across all API routes with proper HTTP status codes and exception hierarchy",
                "effort_hours": 0,
            },
            {
                "component_name": "API Documentation", 
                "status": "Fully Working",
                "notes": "Full OpenAPI/Swagger documentation implemented for all 50+ endpoints with detailed models",
                "effort_hours": 0,
            },
            {
                "component_name": "WebSocket Support",
                "status": "Fully Working", 
                "notes": "WebSocket infrastructure implemented and integrated into main API application",
                "effort_hours": 0,
            },
        ]
        
        success_count = 0
        for update in api_updates:
            if self.update_component_status(**update):
                success_count += 1
            else:
                print(f"Failed to update: {update['component_name']}")
        
        print(f"\n✅ Successfully updated {success_count}/{len(api_updates)} API components")
        return success_count == len(api_updates)


def main():
    """Main CLI interface."""
    parser = argparse.ArgumentParser(description="Update component status in neuroca database")
    parser.add_argument("--component-name", help="Name of component to update")
    parser.add_argument("--status", help="New status for component")
    parser.add_argument("--notes", help="Additional notes for the update")
    parser.add_argument("--priority", help="New priority (Critical, High, Medium, Low)")
    parser.add_argument("--effort-hours", type=int, help="New effort hours estimate")
    parser.add_argument("--updated-by", default="manual_update", help="Who made the update")
    parser.add_argument("--batch-api", action="store_true", help="Update all API components to Fully Working")
    parser.add_argument("--db-path", default="neuroca_temporal_analysis.db", help="Path to database file")
    
    args = parser.parse_args()
    
    # Validate required arguments for non-batch mode
    if not args.batch_api and (not args.component_name or not args.status):
        parser.error("--component-name and --status are required unless using --batch-api")
    
    # Check database exists
    if not Path(args.db_path).exists():
        print(f"Error: Database file not found: {args.db_path}")
        sys.exit(1)
    
    updater = ComponentStatusUpdater(args.db_path)
    
    if args.batch_api:
        success = updater.batch_update_api_components()
    else:
        success = updater.update_component_status(
            component_name=args.component_name,
            status=args.status,
            notes=args.notes,
            priority=args.priority,
            effort_hours=args.effort_hours,
            updated_by=args.updated_by,
        )
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
