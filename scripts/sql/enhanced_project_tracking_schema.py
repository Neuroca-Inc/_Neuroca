#!/usr/bin/env python3
"""
Enhanced Project Tracking Database Schema
Comprehensive template for tracking all aspects of software project health
"""

import sqlite3
from datetime import datetime

def create_enhanced_schema():
    """Create comprehensive project tracking database schema."""
    
    print("🏗️ CREATING ENHANCED PROJECT TRACKING SCHEMA")
    print("=" * 60)
    
    # Connect to database
    conn = sqlite3.connect("enhanced_project_tracking_template.db")
    conn.execute("PRAGMA foreign_keys = ON")
    
    # Create enhanced tables
    create_tables = [
        
        # ============ CORE PROJECT STRUCTURE ============
        
        """
        -- Projects (for multi-project tracking)
        CREATE TABLE IF NOT EXISTS projects (
            project_id INTEGER PRIMARY KEY,
            project_name TEXT NOT NULL UNIQUE,
            project_description TEXT,
            project_type TEXT CHECK(project_type IN ('Web App', 'Mobile App', 'API', 'Library', 'Desktop App', 'AI/ML', 'Data Pipeline', 'Infrastructure')),
            programming_languages TEXT, -- JSON array
            primary_framework TEXT,
            repository_url TEXT,
            project_status TEXT CHECK(project_status IN ('Planning', 'Active Development', 'Maintenance', 'Deprecated', 'Archived')),
            start_date DATE,
            target_completion_date DATE,
            actual_completion_date DATE,
            project_lead TEXT,
            team_size INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            is_active BOOLEAN DEFAULT TRUE,
            version INTEGER DEFAULT 1
        )
        """,
        
        # ============ CODE QUALITY & METRICS ============
        
        """
        -- Code Quality Metrics
        CREATE TABLE IF NOT EXISTS code_quality_metrics (
            metric_id INTEGER PRIMARY KEY,
            project_id INTEGER NOT NULL,
            component_id INTEGER,
            metric_type TEXT CHECK(metric_type IN ('Lines of Code', 'Cyclomatic Complexity', 'Test Coverage', 'Code Duplication', 'Technical Debt Hours', 'Maintainability Index', 'Code Smells')),
            metric_value REAL NOT NULL,
            metric_unit TEXT, -- lines, percentage, hours, count
            measurement_date DATE DEFAULT CURRENT_DATE,
            trend TEXT CHECK(trend IN ('Improving', 'Stable', 'Declining')),
            threshold_min REAL,
            threshold_max REAL,
            status TEXT CHECK(status IN ('Excellent', 'Good', 'Warning', 'Critical')),
            notes TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects(project_id),
            FOREIGN KEY (component_id) REFERENCES components(component_id)
        )
        """,
        
        # ============ DEPENDENCIES & RELATIONSHIPS ============
        
        """
        -- Component Dependencies
        CREATE TABLE IF NOT EXISTS component_dependencies (
            dependency_id INTEGER PRIMARY KEY,
            project_id INTEGER NOT NULL,
            source_component_id INTEGER NOT NULL,
            target_component_id INTEGER NOT NULL,
            dependency_type TEXT CHECK(dependency_type IN ('Hard Dependency', 'Soft Dependency', 'Interface', 'Data Flow', 'Event', 'Service Call')),
            dependency_strength TEXT CHECK(dependency_strength IN ('Critical', 'High', 'Medium', 'Low')),
            is_circular BOOLEAN DEFAULT FALSE,
            notes TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects(project_id),
            FOREIGN KEY (source_component_id) REFERENCES components(component_id),
            FOREIGN KEY (target_component_id) REFERENCES components(component_id)
        )
        """,
        
        """
        -- External Dependencies (libraries, services, APIs)
        CREATE TABLE IF NOT EXISTS external_dependencies (
            external_dep_id INTEGER PRIMARY KEY,
            project_id INTEGER NOT NULL,
            component_id INTEGER,
            dependency_name TEXT NOT NULL,
            dependency_type TEXT CHECK(dependency_type IN ('Library', 'Framework', 'API Service', 'Database', 'Infrastructure', 'Tool')),
            version_current TEXT,
            version_latest TEXT,
            is_security_critical BOOLEAN DEFAULT FALSE,
            last_updated DATE,
            eol_date DATE,
            vulnerability_count INTEGER DEFAULT 0,
            license_type TEXT,
            usage_purpose TEXT,
            replacement_options TEXT,
            health_status TEXT CHECK(health_status IN ('Healthy', 'Outdated', 'Vulnerable', 'EOL', 'Deprecated')),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects(project_id),
            FOREIGN KEY (component_id) REFERENCES components(component_id)
        )
        """,
        
        # ============ DEVELOPMENT VELOCITY & PRODUCTIVITY ============
        
        """
        -- Development Velocity Tracking
        CREATE TABLE IF NOT EXISTS development_velocity (
            velocity_id INTEGER PRIMARY KEY,
            project_id INTEGER NOT NULL,
            sprint_period TEXT, -- "2025-Q1-Sprint-1"
            period_start DATE,
            period_end DATE,
            story_points_planned INTEGER,
            story_points_completed INTEGER,
            features_planned INTEGER,
            features_completed INTEGER,
            bugs_created INTEGER,
            bugs_resolved INTEGER,
            code_commits INTEGER,
            deployment_count INTEGER,
            team_capacity_hours REAL,
            actual_hours_worked REAL,
            velocity_score REAL, -- calculated metric
            quality_score REAL, -- based on bugs/features ratio
            notes TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects(project_id)
        )
        """,
        
        # ============ RISK & TECHNICAL DEBT ============
        
        """
        -- Risk Register
        CREATE TABLE IF NOT EXISTS project_risks (
            risk_id INTEGER PRIMARY KEY,
            project_id INTEGER NOT NULL,
            component_id INTEGER,
            risk_title TEXT NOT NULL,
            risk_description TEXT,
            risk_category TEXT CHECK(risk_category IN ('Technical', 'Security', 'Performance', 'Scalability', 'Maintainability', 'Business', 'External', 'Resource')),
            probability TEXT CHECK(probability IN ('Very Low', 'Low', 'Medium', 'High', 'Very High')),
            impact TEXT CHECK(impact IN ('Very Low', 'Low', 'Medium', 'High', 'Very High')),
            risk_score INTEGER, -- calculated from probability * impact
            mitigation_strategy TEXT,
            mitigation_status TEXT CHECK(mitigation_status IN ('Not Started', 'In Progress', 'Completed', 'Accepted')),
            owner TEXT,
            target_resolution_date DATE,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            resolved_at DATETIME,
            FOREIGN KEY (project_id) REFERENCES projects(project_id),
            FOREIGN KEY (component_id) REFERENCES components(component_id)
        )
        """,
        
        """
        -- Technical Debt Items
        CREATE TABLE IF NOT EXISTS technical_debt (
            debt_id INTEGER PRIMARY KEY,
            project_id INTEGER NOT NULL,
            component_id INTEGER,
            debt_title TEXT NOT NULL,
            debt_description TEXT,
            debt_type TEXT CHECK(debt_type IN ('Code Quality', 'Architecture', 'Performance', 'Security', 'Documentation', 'Testing', 'Infrastructure')),
            estimated_effort_hours REAL,
            business_impact TEXT CHECK(business_impact IN ('Critical', 'High', 'Medium', 'Low')),
            technical_impact TEXT CHECK(technical_impact IN ('Critical', 'High', 'Medium', 'Low')),
            accrual_rate TEXT CHECK(accrual_rate IN ('Fast', 'Medium', 'Slow', 'Stable')),
            resolution_strategy TEXT,
            priority_score INTEGER,
            status TEXT CHECK(status IN ('Identified', 'Planned', 'In Progress', 'Resolved', 'Accepted')),
            owner TEXT,
            target_resolution_date DATE,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            resolved_at DATETIME,
            FOREIGN KEY (project_id) REFERENCES projects(project_id),
            FOREIGN KEY (component_id) REFERENCES components(component_id)
        )
        """,
        
        # ============ TESTING & QUALITY ASSURANCE ============
        
        """
        -- Test Coverage & Quality
        CREATE TABLE IF NOT EXISTS test_coverage (
            coverage_id INTEGER PRIMARY KEY,
            project_id INTEGER NOT NULL,
            component_id INTEGER,
            test_type TEXT CHECK(test_type IN ('Unit', 'Integration', 'End-to-End', 'Performance', 'Security', 'API', 'Manual')),
            lines_covered INTEGER,
            lines_total INTEGER,
            coverage_percentage REAL,
            test_count INTEGER,
            passing_tests INTEGER,
            failing_tests INTEGER,
            flaky_tests INTEGER,
            test_execution_time_ms INTEGER,
            last_run_date DATETIME,
            quality_gate_passed BOOLEAN,
            notes TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects(project_id),
            FOREIGN KEY (component_id) REFERENCES components(component_id)
        )
        """,
        
        # ============ DEPLOYMENT & OPERATIONS ============
        
        """
        -- Deployment Tracking
        CREATE TABLE IF NOT EXISTS deployments (
            deployment_id INTEGER PRIMARY KEY,
            project_id INTEGER NOT NULL,
            environment TEXT CHECK(environment IN ('Development', 'Testing', 'Staging', 'Production', 'Demo')),
            version TEXT NOT NULL,
            git_commit_hash TEXT,
            deployment_date DATETIME DEFAULT CURRENT_TIMESTAMP,
            deployment_status TEXT CHECK(deployment_status IN ('Success', 'Failed', 'Rolled Back', 'In Progress')),
            deployer TEXT,
            deployment_duration_minutes INTEGER,
            components_deployed TEXT, -- JSON array of component IDs
            issues_found INTEGER DEFAULT 0,
            rollback_reason TEXT,
            notes TEXT,
            FOREIGN KEY (project_id) REFERENCES projects(project_id)
        )
        """,
        
        """
        -- Performance Monitoring
        CREATE TABLE IF NOT EXISTS performance_metrics (
            perf_id INTEGER PRIMARY KEY,
            project_id INTEGER NOT NULL,
            component_id INTEGER,
            metric_name TEXT NOT NULL,
            metric_value REAL NOT NULL,
            metric_unit TEXT, -- ms, MB, requests/sec, etc.
            measurement_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            environment TEXT,
            baseline_value REAL,
            threshold_warning REAL,
            threshold_critical REAL,
            status TEXT CHECK(status IN ('Excellent', 'Good', 'Warning', 'Critical')),
            FOREIGN KEY (project_id) REFERENCES projects(project_id),
            FOREIGN KEY (component_id) REFERENCES components(component_id)
        )
        """,
        
        # ============ TEAM & KNOWLEDGE MANAGEMENT ============
        
        """
        -- Component Ownership & Expertise
        CREATE TABLE IF NOT EXISTS component_ownership (
            ownership_id INTEGER PRIMARY KEY,
            project_id INTEGER NOT NULL,
            component_id INTEGER NOT NULL,
            owner_name TEXT NOT NULL,
            owner_role TEXT CHECK(owner_role IN ('Primary Owner', 'Secondary Owner', 'Contributor', 'Expert', 'Learning')),
            expertise_level TEXT CHECK(expertise_level IN ('Expert', 'Proficient', 'Basic', 'Learning')),
            availability TEXT CHECK(availability IN ('Full Time', 'Part Time', 'Occasional', 'Limited')),
            last_worked_date DATE,
            notes TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects(project_id),
            FOREIGN KEY (component_id) REFERENCES components(component_id)
        )
        """,
        
        """
        -- Knowledge Base & Documentation
        CREATE TABLE IF NOT EXISTS knowledge_base (
            knowledge_id INTEGER PRIMARY KEY,
            project_id INTEGER NOT NULL,
            component_id INTEGER,
            knowledge_type TEXT CHECK(knowledge_type IN ('API Documentation', 'Architecture Guide', 'Setup Instructions', 'Troubleshooting', 'Best Practices', 'Decision Record', 'Tutorial', 'FAQ')),
            title TEXT NOT NULL,
            content_url TEXT,
            is_up_to_date BOOLEAN DEFAULT TRUE,
            last_reviewed_date DATE,
            reviewer TEXT,
            importance TEXT CHECK(importance IN ('Critical', 'High', 'Medium', 'Low')),
            target_audience TEXT, -- 'Developers', 'Ops', 'Product', 'All'
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects(project_id),
            FOREIGN KEY (component_id) REFERENCES components(component_id)
        )
        """,
        
        # ============ PROJECT PLANNING & ROADMAP ============
        
        """
        -- Milestones & Releases
        CREATE TABLE IF NOT EXISTS milestones (
            milestone_id INTEGER PRIMARY KEY,
            project_id INTEGER NOT NULL,
            milestone_name TEXT NOT NULL,
            milestone_type TEXT CHECK(milestone_type IN ('Release', 'Feature Complete', 'Beta', 'Alpha', 'MVP', 'Proof of Concept')),
            planned_date DATE,
            actual_date DATE,
            status TEXT CHECK(status IN ('Planning', 'In Progress', 'Completed', 'Delayed', 'Cancelled')),
            completion_percentage INTEGER DEFAULT 0,
            success_criteria TEXT,
            deliverables TEXT, -- JSON array
            stakeholders TEXT, -- JSON array
            notes TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects(project_id)
        )
        """,
        
        """
        -- Features & Epics
        CREATE TABLE IF NOT EXISTS features (
            feature_id INTEGER PRIMARY KEY,
            project_id INTEGER NOT NULL,
            milestone_id INTEGER,
            feature_name TEXT NOT NULL,
            feature_description TEXT,
            feature_type TEXT CHECK(feature_type IN ('Epic', 'Feature', 'User Story', 'Technical Task', 'Bug Fix', 'Enhancement')),
            business_value TEXT CHECK(business_value IN ('Critical', 'High', 'Medium', 'Low')),
            estimated_effort_points INTEGER,
            actual_effort_points INTEGER,
            assigned_components TEXT, -- JSON array of component IDs
            status TEXT CHECK(status IN ('Backlog', 'Planning', 'In Progress', 'Testing', 'Completed', 'Cancelled')),
            assignee TEXT,
            start_date DATE,
            completion_date DATE,
            acceptance_criteria TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects(project_id),
            FOREIGN KEY (milestone_id) REFERENCES milestones(milestone_id)
        )
        """,
        
        # ============ QUALITY GATES & COMPLIANCE ============
        
        """
        -- Quality Gates
        CREATE TABLE IF NOT EXISTS quality_gates (
            gate_id INTEGER PRIMARY KEY,
            project_id INTEGER NOT NULL,
            gate_name TEXT NOT NULL,
            gate_type TEXT CHECK(gate_type IN ('Build', 'Test', 'Security', 'Performance', 'Code Quality', 'Documentation', 'Deployment')),
            criteria TEXT NOT NULL, -- JSON object with criteria and thresholds
            is_mandatory BOOLEAN DEFAULT TRUE,
            last_check_date DATETIME,
            last_result TEXT CHECK(last_result IN ('Pass', 'Fail', 'Warning', 'Not Run')),
            pass_rate_percentage REAL,
            notes TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects(project_id)
        )
        """
    ]
    
    # Execute all table creation statements
    for i, table_sql in enumerate(create_tables, 1):
        try:
            conn.execute(table_sql)
            table_name = table_sql.split("CREATE TABLE IF NOT EXISTS ")[1].split(" (")[0]
            print(f"   ✅ {i:2d}. Created table: {table_name}")
        except Exception as e:
            print(f"   ❌ {i:2d}. Failed to create table: {e}")
    
    # Create views for comprehensive reporting
    create_views = [
        """
        -- Project Health Dashboard
        CREATE VIEW IF NOT EXISTS project_health_dashboard AS
        SELECT 
            p.project_name,
            p.project_status,
            COUNT(c.component_id) as total_components,
            SUM(CASE WHEN cua.working_status = 'Fully Working' THEN 1 ELSE 0 END) as working_components,
            ROUND(
                (SUM(CASE WHEN cua.working_status = 'Fully Working' THEN 1 ELSE 0 END) * 100.0) / COUNT(c.component_id), 
                1
            ) as completion_percentage,
            COUNT(pr.risk_id) as active_risks,
            COUNT(td.debt_id) as technical_debt_items,
            AVG(cqm.metric_value) as avg_quality_score
        FROM projects p
        LEFT JOIN components c ON p.project_id = c.project_id
        LEFT JOIN component_usage_analysis cua ON c.component_id = cua.component_id
        LEFT JOIN project_risks pr ON p.project_id = pr.project_id AND pr.resolved_at IS NULL
        LEFT JOIN technical_debt td ON p.project_id = td.project_id AND td.status != 'Resolved'
        LEFT JOIN code_quality_metrics cqm ON p.project_id = cqm.project_id AND cqm.metric_type = 'Maintainability Index'
        WHERE p.is_active = TRUE
        GROUP BY p.project_id, p.project_name, p.project_status
        """,
        
        """
        -- Component Risk Assessment
        CREATE VIEW IF NOT EXISTS component_risk_assessment AS
        SELECT 
            c.component_name,
            c.category_name,
            COUNT(pr.risk_id) as risk_count,
            COUNT(td.debt_id) as debt_count,
            AVG(CASE WHEN pr.risk_score IS NOT NULL THEN pr.risk_score ELSE 0 END) as avg_risk_score,
            MAX(cqm.metric_value) as quality_score,
            cua.working_status,
            CASE 
                WHEN COUNT(pr.risk_id) > 3 OR AVG(pr.risk_score) > 15 THEN 'High Risk'
                WHEN COUNT(pr.risk_id) > 1 OR AVG(pr.risk_score) > 8 THEN 'Medium Risk'
                ELSE 'Low Risk'
            END as overall_risk_level
        FROM components c
        LEFT JOIN component_usage_analysis cua ON c.component_id = cua.component_id
        LEFT JOIN project_risks pr ON c.component_id = pr.component_id AND pr.resolved_at IS NULL
        LEFT JOIN technical_debt td ON c.component_id = td.component_id AND td.status != 'Resolved'
        LEFT JOIN code_quality_metrics cqm ON c.component_id = cqm.component_id AND cqm.metric_type = 'Maintainability Index'
        WHERE c.is_active = TRUE
        GROUP BY c.component_id, c.component_name, c.category_name, cua.working_status
        """
    ]
    
    for view_sql in create_views:
        try:
            conn.execute(view_sql)
            view_name = view_sql.split("CREATE VIEW IF NOT EXISTS ")[1].split(" AS")[0]
            print(f"   ✅ Created view: {view_name}")
        except Exception as e:
            print(f"   ❌ Failed to create view: {e}")
    
    conn.commit()
    conn.close()
    
    print(f"\n🎉 ENHANCED SCHEMA CREATED SUCCESSFULLY!")
    print(f"   📊 Database: enhanced_project_tracking_template.db")
    print(f"   📋 Total Tables: {len(create_tables)}")
    print(f"   📈 Views: {len(create_views)}")
    
    return True

if __name__ == "__main__":
    create_enhanced_schema()
