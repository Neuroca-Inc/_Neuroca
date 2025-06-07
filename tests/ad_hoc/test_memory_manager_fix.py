#!/usr/bin/env python3
"""
Test script to reproduce and verify MemoryManager constructor issues
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def test_memory_manager_basic():
    """Test basic MemoryManager instantiation"""
    print("=== Testing MemoryManager Basic Instantiation ===")
    
    try:
        from neuroca.memory.manager.memory_manager import MemoryManager
        from neuroca.memory.backends import BackendType
        
        print("✅ Successfully imported MemoryManager and BackendType")
        
        # Test 1: Simple instantiation with backend_type
        print("\nTest 1: Simple instantiation with backend_type")
        manager1 = MemoryManager(backend_type=BackendType.MEMORY)
        print("✅ MemoryManager instantiated with backend_type")
        
        # Test 2: Instantiation with config
        print("\nTest 2: Instantiation with config")
        config = {"ttl_seconds": 3600}
        manager2 = MemoryManager(config=config, backend_type=BackendType.MEMORY)
        print("✅ MemoryManager instantiated with config")
        
        # Test 3: Initialize the manager
        print("\nTest 3: Initialize manager")
        import asyncio
        
        async def test_init():
            await manager1.initialize()
            print("✅ MemoryManager initialized successfully")
            await manager1.shutdown()
            print("✅ MemoryManager shutdown successfully")
        
        asyncio.run(test_init())
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_missing_imports():
    """Test for missing imports that might cause issues"""
    print("\n=== Testing Import Dependencies ===")
    
    missing_imports = []
    
    # Test core imports
    try:
        from neuroca.memory.backends.factory import BackendType, StorageBackendFactory
        print("✅ Backend factory imports OK")
    except ImportError as e:
        missing_imports.append(f"Backend factory: {e}")
    
    try:
        from neuroca.memory.models.memory_item import MemoryItem
        print("✅ Memory models imports OK")
    except ImportError as e:
        missing_imports.append(f"Memory models: {e}")
    
    try:
        from neuroca.memory.tiers.stm.core import ShortTermMemoryTier
        from neuroca.memory.tiers.mtm.core import MediumTermMemoryTier
        from neuroca.memory.tiers.ltm.core import LongTermMemoryTier
        print("✅ Memory tiers imports OK")
    except ImportError as e:
        missing_imports.append(f"Memory tiers: {e}")
    
    if missing_imports:
        print(f"\n❌ Found {len(missing_imports)} missing imports:")
        for imp in missing_imports:
            print(f"  - {imp}")
        return False
    else:
        print("✅ All core imports available")
        return True

if __name__ == "__main__":
    print("NCA Memory Manager Fix Test")
    print("=" * 50)
    
    # Test imports first
    imports_ok = test_missing_imports()
    
    if imports_ok:
        # Test basic functionality
        basic_ok = test_memory_manager_basic()
        
        if basic_ok:
            print("\n🎉 All tests passed! MemoryManager is working.")
        else:
            print("\n💥 Basic functionality tests failed.")
    else:
        print("\n💥 Import tests failed - fixing imports first.")
