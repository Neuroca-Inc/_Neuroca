#!/usr/bin/env python3
"""
Project Health Monitor - Easy-to-use script for checking NEUROCA project status.
This is your main dashboard for seeing what needs attention.
"""

import sqlite3
import pandas as pd
from datetime import datetime

def show_project_health():
    """Show comprehensive project health dashboard."""
    
    print("🏥 NEUROCA PROJECT HEALTH MONITOR")
    print("=" * 60)
    print(f"Report Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    with sqlite3.connect("neuroca_temporal_analysis.db") as conn:
        
        # 1. Critical Issues (What needs immediate attention)
        print(f"\n🚨 IMMEDIATE ACTION REQUIRED:")
        print("-" * 40)
        
        critical_issues = pd.read_sql_query("""
            SELECT component_name, working_status, priority_to_fix, missing_dependencies
            FROM critical_blockers
            ORDER BY 
                CASE priority_to_fix 
                    WHEN 'CRITICAL' THEN 1 
                    WHEN 'HIGH' THEN 2 
                    ELSE 3 
                END
        """, conn)
        
        if not critical_issues.empty:
            for i, row in critical_issues.iterrows():
                print(f"   🔥 {row['component_name']}: {row['working_status']} ({row['priority_to_fix']})")
                print(f"      Issue: {row['missing_dependencies']}")
        else:
            print("   ✅ No critical issues - great job!")
        
        # 2. Priority Dashboard (Work planning)
        print(f"\n🎯 WORK PRIORITIZATION:")
        print("-" * 30)
        
        dashboard = pd.read_sql_query("SELECT * FROM priority_dashboard", conn)
        for _, row in dashboard.iterrows():
            urgency, count, components = row['urgency_level'], row['component_count'], row['components']
            if count > 0:
                icon = {"IMMEDIATE_ACTION": "🔥", "NEXT_SPRINT": "⏳", "TECHNICAL_DEBT": "🔧", "WORKING_WELL": "✅"}.get(urgency, "📋")
                print(f"   {icon} {urgency}: {count} components")
                if urgency == "IMMEDIATE_ACTION" and count <= 3:
                    print(f"      → {components}")
        
        # 3. Bug Detection (Auto-detected issues)
        print(f"\n🔍 AUTOMATED BUG DETECTION:")
        print("-" * 35)
        
        bugs = pd.read_sql_query("""
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
            LIMIT 5
        """, conn)
        
        if not bugs.empty:
            for _, row in bugs.iterrows():
                severity_icon = {"CRITICAL": "💀", "HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🔵"}.get(row['severity'], "⚪")
                print(f"   {severity_icon} [{row['severity']}] {row['component_name']}")
                print(f"      {row['description']}")
        else:
            print("   ✅ No automated bugs detected")
        
        # 4. Component Stability (Development quality)
        print(f"\n📊 COMPONENT STABILITY:")
        print("-" * 25)
        
        stability = pd.read_sql_query("""
            SELECT component_name, stability_rating, change_count, activity_level
            FROM component_stability_analysis 
            WHERE stability_rating != 'STABLE' OR activity_level = 'HIGH_ACTIVITY'
            ORDER BY change_count DESC
            LIMIT 3
        """, conn)
        
        if not stability.empty:
            for _, row in stability.iterrows():
                rating_icon = {"UNSTABLE": "🔴", "MODERATE": "🟡", "STABLE": "🟢"}.get(row['stability_rating'], "⚪")
                print(f"   {rating_icon} {row['component_name']}: {row['stability_rating']} ({row['change_count']} changes)")
        else:
            print("   ✅ All components are stable")
        
        # 5. Quick Stats
        print(f"\n📈 QUICK STATISTICS:")
        print("-" * 20)
        
        stats = {}
        stats['Total Components'] = conn.execute("SELECT COUNT(*) FROM components WHERE is_active = TRUE").fetchone()[0]
        stats['Fully Working'] = conn.execute("SELECT COUNT(*) FROM component_usage_analysis WHERE working_status = 'Fully Working' AND is_active = TRUE").fetchone()[0]
        stats['Need Fixing'] = conn.execute("SELECT COUNT(*) FROM component_usage_analysis WHERE working_status IN ('Broken', 'Missing') AND is_active = TRUE").fetchone()[0]
        stats['In Progress'] = conn.execute("SELECT COUNT(*) FROM component_usage_analysis WHERE working_status IN ('Partially Working', 'Exists But Not Connected') AND is_active = TRUE").fetchone()[0]
        
        completion_rate = round((stats['Fully Working'] / stats['Total Components']) * 100, 1) if stats['Total Components'] > 0 else 0
        
        for key, value in stats.items():
            print(f"   {key}: {value}")
        print(f"   Completion Rate: {completion_rate}%")
        
        # 6. Recommendations
        print(f"\n💡 RECOMMENDATIONS:")
        print("-" * 20)
        
        if not critical_issues.empty:
            print(f"   1. Focus on {len(critical_issues)} critical blocker(s) first")
        else:
            print(f"   1. ✅ No critical blockers - good to proceed")
        
        next_sprint = dashboard[dashboard['urgency_level'] == 'NEXT_SPRINT']['component_count'].iloc[0] if len(dashboard) > 0 else 0
        if next_sprint > 0:
            print(f"   2. Plan {next_sprint} components for next development sprint")
        
        tech_debt = dashboard[dashboard['urgency_level'] == 'TECHNICAL_DEBT']['component_count'].iloc[0] if len(dashboard) > 0 else 0
        if tech_debt > 0:
            print(f"   3. Schedule {tech_debt} technical debt items for future cleanup")
        
        if completion_rate >= 75:
            print(f"   4. 🎉 Project is in good shape ({completion_rate}% complete)")
        elif completion_rate >= 50:
            print(f"   4. Project making good progress ({completion_rate}% complete)")
        else:
            print(f"   4. Focus on core functionality ({completion_rate}% complete)")

def show_available_views():
    """Show what database views are available for detailed analysis."""
    
    print(f"\n🔧 AVAILABLE DETAILED VIEWS:")
    print("-" * 35)
    print("   📊 bug_detection_report - All detected issues")
    print("   📈 component_stability_analysis - Change tracking")  
    print("   🎯 priority_dashboard - Work prioritization")
    print("   📋 critical_blockers - Immediate issues only")
    print("   📋 data_quality_report - Database health")
    print("   📋 component_change_history - Full audit trail")
    
    print(f"\n💻 SQL EXAMPLES:")
    print("   sqlite3 neuroca_temporal_analysis.db \"SELECT * FROM critical_blockers;\"")
    print("   sqlite3 neuroca_temporal_analysis.db \"SELECT * FROM bug_detection_report;\"")
    print("   sqlite3 neuroca_temporal_analysis.db \"SELECT * FROM priority_dashboard;\"")

if __name__ == "__main__":
    show_project_health()
    show_available_views()
