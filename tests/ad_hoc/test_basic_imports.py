#!/usr/bin/env python3
"""
Simple test to check if imports work.
"""

print("Starting import test...")

import sys
sys.path.insert(0, 'src')

try:
    print("Importing ScopeConfig...")
    from src.neuroca.analysis.summarization_engine import ScopeConfig
    print("✅ ScopeConfig imported")
    
    print("Importing CodebaseSummarizationEngine...")
    from src.neuroca.analysis.summarization_engine import CodebaseSummarizationEngine
    print("✅ CodebaseSummarizationEngine imported")
    
    print("Creating scope config...")
    scope = ScopeConfig(repos=["main"], branches=["main"])
    print("✅ ScopeConfig created")
    
    print("Creating engine...")
    engine = CodebaseSummarizationEngine(scope, ".")
    print("✅ Engine created")
    
    print("🎉 All imports and creation successful!")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
