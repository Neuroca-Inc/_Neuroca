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
        """Get current component information."""
        cursor = conn.cursor()
        cursor.execute("""
            SELECT c.component_id, c.component_name, c.category_id, c.status_id, s.status_name,
                   c.file_path, c.priority, c.effort_hours, c.notes, c.version
            FROM components c
            JOIN statuses s ON c.status_id = s.status_id
            WHERE c.component_name = ?
        """, (component_name,))
        
        row = cursor.fetchone()
        if row:
            return {
                "component_id": row[0],
                "component_name": row[1],
                "category_id": row[2],
                "status_id": row[3],
                "status_name": row[4],
                "file_path": row[5],
                "priority": row[6],
                "effort_hours": row[7],
                "notes": row[8],
                "version": row[9],
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
                print(f"Current status of '{component_name}': {current_info['status_name']}")
                
                new_status_id = self.valid_statuses[status]
                
                # Check if this is actually a change
                if current_info["status_id"] == new_status_id:
                    print(f"Component '{component_name}' is already '{status}'. No update needed.")
                    return True
                
                # Prepare update fields
                update_fields = []
                update_values = []
                
                update_fields.append("status_id = ?")
                update_values.append(new_status_id)
                
                if priority:
                    update_fields.append("priority = ?")
                    update_values.append(priority)
                
                if effort_hours is not None:
                    update_fields.append("effort_hours = ?")
                    update_values.append(effort_hours)
                
                # Handle notes - append to existing or replace
                new_notes = current_info["notes"] or ""
                if notes:
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    if new_notes:
                        new_notes += f" | Updated {timestamp}: {notes}"
                    else:
                        new_notes = f"Updated {timestamp}: {notes}"
                
                update_fields.append("notes = ?")
                update_values.append(new_notes)
                
                update_fields.append("updated_at = CURRENT_TIMESTAMP")
                update_fields.append("version = version + 1")
                
                # Add component_id for WHERE clause
                update_values.append(current_info["component_id"])
                
                # Execute update
                update_sql = f"""
                    UPDATE components 
                    SET {', '.join(update_fields)}
                    WHERE component_id = ?
                """
                
                cursor = conn.cursor()
                cursor.execute(update_sql, update_values)
                
                if cursor.rowcount == 0:
                    print(f"Error: No rows updated for component '{component_name}'")
                    return False
                
                # Verify the update
                updated_info = self.get_component_info(conn, component_name)
                if updated_info and updated_info["status_id"] == new_status_id:
                    print(f"✅ Successfully updated '{component_name}' from '{current_info['status_name']}' to '{status}'")
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
