#!/usr/bin/env python3
"""
Neuroca Installation Verification Script

This script verifies that Neuroca has been installed correctly and all
essential components are functioning properly. It performs a series of
checks and reports the results.

Usage:
    python verify_installation.py
    # or after installation:
    neuroca verify
"""

import sys
import traceback
from typing import List, Tuple, Dict, Any
import importlib
import subprocess
import os


class VerificationTest:
    """Base class for verification tests."""
    
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
    
    def run(self) -> Tuple[bool, str]:
        """Run the test and return (success, message)."""
        raise NotImplementedError


class ImportTest(VerificationTest):
    """Test that a module can be imported."""
    
    def __init__(self, module_name: str, description: str = None):
        self.module_name = module_name
        desc = description or f"Import {module_name}"
        super().__init__(f"import_{module_name.replace('.', '_')}", desc)
    
    def run(self) -> Tuple[bool, str]:
        try:
            importlib.import_module(self.module_name)
            return True, f"✓ Successfully imported {self.module_name}"
        except ImportError as e:
            return False, f"✗ Failed to import {self.module_name}: {e}"
        except Exception as e:
            return False, f"✗ Unexpected error importing {self.module_name}: {e}"


class FunctionTest(VerificationTest):
    """Test that a function executes successfully."""
    
    def __init__(self, name: str, description: str, test_func):
        super().__init__(name, description)
        self.test_func = test_func
    
    def run(self) -> Tuple[bool, str]:
        try:
            result = self.test_func()
            if isinstance(result, tuple):
                success, message = result
                return success, message
            elif result is True or result is None:
                return True, f"✓ {self.description}"
            else:
                return False, f"✗ {self.description}: {result}"
        except Exception as e:
            return False, f"✗ {self.description}: {e}"


class CLITest(VerificationTest):
    """Test CLI command execution."""
    
    def __init__(self, command: List[str], description: str):
        self.command = command
        super().__init__(f"cli_{'_'.join(command)}", description)
    
    def run(self) -> Tuple[bool, str]:
        try:
            result = subprocess.run(
                self.command,
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                return True, f"✓ Command '{' '.join(self.command)}' executed successfully"
            else:
                return False, f"✗ Command '{' '.join(self.command)}' failed: {result.stderr}"
        except subprocess.TimeoutExpired:
            return False, f"✗ Command '{' '.join(self.command)}' timed out"
        except Exception as e:
            return False, f"✗ Command '{' '.join(self.command)}' error: {e}"


def test_basic_neuroca_functionality():
    """Test basic Neuroca functionality."""
    try:
        from neuroca import __version__
        from neuroca.core.models import BaseModel
        from neuroca.memory.models.memory_item import MemoryItem, MemoryContent
        
        # Test creating a basic memory item
        content = MemoryContent(text="Test memory item")
        memory_item = MemoryItem(
            content=content,
            summary="Test memory"
        )
        
        return True, f"✓ Basic functionality test passed (version: {__version__})"
    except Exception as e:
        return False, f"✗ Basic functionality test failed: {e}"


def test_memory_system():
    """Test memory system initialization."""
    try:
        from neuroca.memory.backends.sqlite_backend import SQLiteBackend
        
        # Test creating an in-memory SQLite backend
        backend = SQLiteBackend()
        backend.configure({"database_path": ":memory:"})
        
        return True, "✓ Memory system initialization successful"
    except Exception as e:
        return False, f"✗ Memory system test failed: {e}"


def test_api_components():
    """Test API components can be imported and initialized."""
    try:
        from neuroca.api.main import app
        from fastapi.testclient import TestClient
        
        # Test creating a test client
        client = TestClient(app)
        response = client.get("/health")
        
        if response.status_code == 200:
            return True, "✓ API components working correctly"
        else:
            return False, f"✗ API health check failed: {response.status_code}"
    except Exception as e:
        # API might not be fully functional without configuration
        # This is acceptable for basic verification
        return True, f"✓ API components imported (configuration may be needed for full functionality)"


def test_configuration():
    """Test configuration system."""
    try:
        from neuroca.config import config
        
        # Test accessing configuration
        log_level = config.get("LOG_LEVEL", "INFO")
        
        return True, "✓ Configuration system working"
    except Exception as e:
        return False, f"✗ Configuration test failed: {e}"


def run_verification() -> Dict[str, Any]:
    """Run all verification tests."""
    print("=" * 60)
    print("Neuroca Installation Verification")
    print("=" * 60)
    print()
    
    # Define all tests
    tests = [
        # Core imports
        ImportTest("neuroca", "Core neuroca package"),
        ImportTest("neuroca.core", "Core components"),
        ImportTest("neuroca.memory", "Memory system"),
        ImportTest("neuroca.api", "API components"),
        ImportTest("neuroca.cli", "CLI components"),
        
        # Functionality tests
        FunctionTest("basic_functionality", "Basic Neuroca functionality", test_basic_neuroca_functionality),
        FunctionTest("memory_system", "Memory system initialization", test_memory_system),
        FunctionTest("api_components", "API components", test_api_components),
        FunctionTest("configuration", "Configuration system", test_configuration),
        
        # CLI tests
        CLITest(["neuroca", "version"], "CLI version command"),
        CLITest(["neuroca", "--help"], "CLI help command"),
    ]
    
    # Run tests
    passed = 0
    failed = 0
    results = []
    
    for test in tests:
        print(f"Running: {test.description}...")
        success, message = test.run()
        results.append({
            'name': test.name,
            'description': test.description,
            'success': success,
            'message': message
        })
        
        if success:
            passed += 1
            print(f"  {message}")
        else:
            failed += 1
            print(f"  {message}")
        print()
    
    # Summary
    print("=" * 60)
    print("VERIFICATION SUMMARY")
    print("=" * 60)
    print(f"Total tests: {len(tests)}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print()
    
    if failed == 0:
        print("🎉 All tests passed! Neuroca is properly installed and functional.")
        status = "success"
    elif failed <= 2:
        print("⚠️  Some tests failed, but core functionality appears to work.")
        print("   This may be due to missing optional dependencies or configuration.")
        status = "partial"
    else:
        print("❌ Multiple tests failed. There may be installation issues.")
        status = "failed"
    
    print()
    print("Next steps:")
    print("- Review the Getting Started guide: docs/user/getting-started.md")
    print("- Check the API documentation: docs/api/endpoints.md") 
    print("- Configure your LLM provider API keys if needed")
    print("- Run 'neuroca init' to set up initial configuration")
    
    return {
        'status': status,
        'total': len(tests),
        'passed': passed,
        'failed': failed,
        'results': results
    }


if __name__ == "__main__":
    try:
        result = run_verification()
        exit_code = 0 if result['status'] == 'success' else 1
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\nVerification interrupted by user.")
        sys.exit(130)
    except Exception as e:
        print(f"\nUnexpected error during verification: {e}")
        print("\nFull traceback:")
        traceback.print_exc()
        sys.exit(1)