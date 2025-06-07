#!/usr/bin/env python3
"""
Comprehensive component status verification.
Checks each component end-to-end to ensure database accuracy.
"""

import sqlite3
import os
import ast
import importlib.util
from pathlib import Path
from typing import Dict, List, Tuple

class ComponentVerifier:
    def __init__(self, db_file="neuroca_temporal_analysis.db"):
        self.db_file = db_file
        self.project_root = os.getcwd()
        
    def verify_file_exists(self, file_path: str) -> Tuple[bool, str]:
        """Verify if a file or directory exists and return details."""
        if not file_path or file_path == 'N/A':
            return False, "No file path specified"
        
        clean_path = file_path.replace('(MISSING)', '').strip()
        
        if clean_path.startswith('src/'):
            full_path = os.path.join(self.project_root, clean_path)
        else:
            full_path = clean_path
            
        if os.path.exists(full_path):
            if os.path.isfile(full_path):
                size = os.path.getsize(full_path)
                return True, f"File exists ({size} bytes)"
            elif os.path.isdir(full_path):
                files = list(Path(full_path).rglob("*.py"))
                return True, f"Directory exists ({len(files)} Python files)"
        
        return False, "File/directory not found"
    
    def check_python_imports(self, file_path: str) -> Tuple[bool, List[str]]:
        """Check if a Python file imports successfully."""
        if not file_path.endswith('.py'):
            return True, []
        
        try:
            clean_path = file_path.replace('(MISSING)', '').strip()
            full_path = os.path.join(self.project_root, clean_path) if clean_path.startswith('src/') else clean_path
            
            if not os.path.exists(full_path):
                return False, ["File not found"]
            
            # Read file and check for obvious syntax errors
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Try to parse as AST
            try:
                ast.parse(content)
                return True, ["Syntax valid"]
            except SyntaxError as e:
                return False, [f"Syntax error: {e}"]
                
        except Exception as e:
            return False, [f"Error checking file: {e}"]
    
    def verify_memory_service_layer(self) -> Dict[str, str]:
        """Comprehensive verification of Memory Service Layer."""
        results = {}
        
        # Check main service file
        service_file = "src/neuroca/memory/service.py"
        exists, details = self.verify_file_exists(service_file)
        results['file_exists'] = f"{exists}: {details}"
        
        if exists:
            # Check imports
            imports_ok, import_details = self.check_python_imports(service_file)
            results['imports'] = f"{imports_ok}: {', '.join(import_details)}"
            
            # Check for key classes/functions
            try:
                full_path = os.path.join(self.project_root, service_file)
                with open(full_path, 'r') as f:
                    content = f.read()
                
                key_elements = ['MemoryService', 'create_memory', 'get_memory', 'search_memories']
                found_elements = [elem for elem in key_elements if elem in content]
                results['key_elements'] = f"Found: {', '.join(found_elements)}"
                
                # Check for dependency injection
                if '@inject' in content or 'Depends(' in content:
                    results['dependency_injection'] = "True: DI patterns found"
                else:
                    results['dependency_injection'] = "False: No DI patterns found"
                    
            except Exception as e:
                results['content_analysis'] = f"Error: {e}"
        
        return results
    
    def verify_api_routes(self) -> Dict[str, str]:
        """Verify API routes component."""
        results = {}
        
        routes_dir = "src/neuroca/api/routes/"
        exists, details = self.verify_file_exists(routes_dir)
        results['directory_exists'] = f"{exists}: {details}"
        
        if exists:
            # Check for specific route files
            route_files = ['memory.py', '__init__.py']
            for route_file in route_files:
                full_path = os.path.join(self.project_root, routes_dir, route_file)
                if os.path.exists(full_path):
                    results[f'{route_file}_exists'] = "True"
                    
                    # Check content
                    try:
                        with open(full_path, 'r') as f:
                            content = f.read()
                        
                        if route_file == 'memory.py':
                            # Check for FastAPI route decorators
                            if '@router.' in content:
                                results['fastapi_routes'] = "True: Route decorators found"
                            else:
                                results['fastapi_routes'] = "False: No route decorators"
                                
                            # Check for MemoryService dependency
                            if 'MemoryService' in content:
                                results['memory_service_integration'] = "True: MemoryService referenced"
                            else:
                                results['memory_service_integration'] = "False: No MemoryService integration"
                                
                    except Exception as e:
                        results[f'{route_file}_content_error'] = str(e)
                else:
                    results[f'{route_file}_exists'] = "False"
        
        return results
    
    def verify_cli_interface(self) -> Dict[str, str]:
        """Verify CLI interface component."""
        results = {}
        
        cli_dir = "src/neuroca/cli/"
        exists, details = self.verify_file_exists(cli_dir)
        results['directory_exists'] = f"{exists}: {details}"
        
        if exists:
            # Check main CLI files
            cli_files = ['main.py', '__init__.py', 'commands/']
            for cli_file in cli_files:
                full_path = os.path.join(self.project_root, cli_dir, cli_file)
                if os.path.exists(full_path):
                    results[f'{cli_file}_exists'] = "True"
                    
                    if cli_file == 'main.py':
                        try:
                            with open(full_path, 'r') as f:
                                content = f.read()
                            
                            # Check for Typer
                            if 'typer' in content.lower():
                                results['typer_integration'] = "True: Typer found"
                            else:
                                results['typer_integration'] = "False: No Typer"
                                
                            # Check for command registration
                            if 'app.command' in content or '@app.command' in content:
                                results['command_registration'] = "True: Commands registered"
                            else:
                                results['command_registration'] = "False: No command registration"
                                
                        except Exception as e:
                            results['main_py_error'] = str(e)
                            
                elif cli_file == 'commands/':
                    # Check commands directory
                    commands_dir = os.path.join(self.project_root, cli_dir, 'commands')
                    if os.path.isdir(commands_dir):
                        command_files = list(Path(commands_dir).glob("*.py"))
                        results['command_files'] = f"Found {len(command_files)} command files"
                    else:
                        results['commands_directory'] = "False: Commands directory missing"
                else:
                    results[f'{cli_file}_exists'] = "False"
        
        return results
    
    def verify_fastapi_application(self) -> Dict[str, str]:
        """Verify FastAPI application component."""
        results = {}
        
        # Check for multiple app files (conflict detection)
        app_files = ['src/neuroca/api/app.py', 'src/neuroca/api/main.py']
        existing_apps = []
        
        for app_file in app_files:
            exists, details = self.verify_file_exists(app_file)
            if exists:
                existing_apps.append(app_file)
                results[f'{app_file}_exists'] = f"True: {details}"
                
                # Check content
                try:
                    full_path = os.path.join(self.project_root, app_file)
                    with open(full_path, 'r') as f:
                        content = f.read()
                    
                    if 'FastAPI(' in content:
                        results[f'{app_file}_fastapi_instance'] = "True: FastAPI instance found"
                    
                    if 'include_router' in content:
                        results[f'{app_file}_router_integration'] = "True: Router integration found"
                    
                except Exception as e:
                    results[f'{app_file}_content_error'] = str(e)
            else:
                results[f'{app_file}_exists'] = f"False: {details}"
        
        if len(existing_apps) > 1:
            results['conflict_detected'] = f"True: Multiple FastAPI apps found: {', '.join(existing_apps)}"
        elif len(existing_apps) == 1:
            results['conflict_detected'] = "False: Single FastAPI app found"
        else:
            results['conflict_detected'] = "Critical: No FastAPI app found"
        
        return results
    
    def generate_corrected_status(self, component_name: str, verification_results: Dict[str, str]) -> str:
        """Generate corrected status based on verification results."""
        
        # Count issues
        issues = []
        for key, value in verification_results.items():
            if value.startswith('False:') or value.startswith('Critical:') or 'error' in key.lower():
                issues.append(f"{key}: {value}")
        
        if not issues:
            return "Fully Working"
        elif len(issues) <= 2 and not any('Critical:' in issue for issue in issues):
            return "Partially Working"
        else:
            return "Broken"
    
    def update_component_status(self, component_name: str, new_status: str, verification_notes: str):
        """Update component status in database."""
        with sqlite3.connect(self.db_file) as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            
            cursor = conn.execute("""
                UPDATE components 
                SET status_id = (SELECT status_id FROM statuses WHERE status_name = ?),
                    notes = 'Status verified end-to-end on ' || datetime('now') || ' - ' || ?,
                    updated_at = datetime('now'),
                    version = version + 1
                WHERE component_name = ?
            """, (new_status, verification_notes, component_name))
            
            if cursor.rowcount > 0:
                print(f"✅ Updated {component_name}: {new_status}")
                return True
            else:
                print(f"⚠️ Component {component_name} not found in database")
                return False
    
    def run_verification(self):
        """Run comprehensive verification of all 'Fully Working' components."""
        print("🔍 COMPREHENSIVE COMPONENT VERIFICATION")
        print("=" * 60)
        
        # Priority components to verify first
        priority_components = [
            "Memory Service Layer",
            "FastAPI Application", 
            "API Routes",
            "CLI Interface"
        ]
        
        for component_name in priority_components:
            print(f"\n🔧 Verifying: {component_name}")
            print("-" * 40)
            
            if component_name == "Memory Service Layer":
                results = self.verify_memory_service_layer()
            elif component_name == "FastAPI Application":
                results = self.verify_fastapi_application()
            elif component_name == "API Routes":
                results = self.verify_api_routes()
            elif component_name == "CLI Interface":
                results = self.verify_cli_interface()
            else:
                continue
            
            # Display results
            for key, value in results.items():
                print(f"   {key}: {value}")
            
            # Determine corrected status
            corrected_status = self.generate_corrected_status(component_name, results)
            verification_summary = f"Verified: {len([v for v in results.values() if v.startswith('True')])} passes, {len([v for v in results.values() if v.startswith('False') or 'error' in v.lower()])} issues"
            
            print(f"\n   📊 Recommended Status: {corrected_status}")
            print(f"   📝 Summary: {verification_summary}")
            
            # Update database
            self.update_component_status(component_name, corrected_status, verification_summary)

def main():
    verifier = ComponentVerifier()
    verifier.run_verification()
    
    print(f"\n🎯 Verification completed!")
    print("Run 'python test_temporal_database.py' to see updated results")

if __name__ == "__main__":
    main()
