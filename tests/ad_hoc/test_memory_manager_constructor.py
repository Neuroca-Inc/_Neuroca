"""
Test to isolate and fix the MemoryManager constructor signature mismatch.
"""

import asyncio
import sys
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from neuroca.memory.backends import BackendType
from neuroca.memory.manager.memory_manager import MemoryManager


async def test_memory_manager_constructor():
    """Test MemoryManager constructor with current parameters."""
    print("Testing MemoryManager constructor...")
    
    try:
        # This is how MemoryManager tries to create STM tier:
        memory_manager = MemoryManager(
            backend_type=BackendType.MEMORY,
            backend_config={},
            config={"stm": {}, "mtm": {}, "ltm": {}},
        )
        
        print("✅ MemoryManager constructor succeeded")
        
        # Try to initialize
        print("Testing MemoryManager initialization...")
        await memory_manager.initialize()
        print("✅ MemoryManager initialization succeeded")
        
        # Cleanup
        await memory_manager.shutdown()
        print("✅ MemoryManager shutdown succeeded")
        
    except Exception as e:
        print(f"❌ MemoryManager failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


if __name__ == "__main__":
    success = asyncio.run(test_memory_manager_constructor())
    sys.exit(0 if success else 1)
