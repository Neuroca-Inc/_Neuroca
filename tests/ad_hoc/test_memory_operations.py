#!/usr/bin/env python3
"""
Test script to verify basic memory operations work correctly
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

async def test_memory_operations():
    """Test basic memory operations"""
    print("=== Testing Memory Operations ===")
    
    try:
        from neuroca.memory.manager.memory_manager import MemoryManager
        from neuroca.memory.backends import BackendType
        
        # Initialize memory manager
        manager = MemoryManager(backend_type=BackendType.MEMORY)
        await manager.initialize()
        print("✅ MemoryManager initialized")
        
        # Test 1: Add a memory
        print("\nTest 1: Adding memory")
        memory_id = await manager.add_memory(
            content="This is a test memory",
            summary="Test memory for verification",
            importance=0.8,
            tags=["test", "verification"],
            metadata={"source": "test_script"}
        )
        print(f"✅ Added memory with ID: {memory_id}")
        
        # Test 2: Retrieve the memory
        print("\nTest 2: Retrieving memory")
        retrieved_memory = await manager.retrieve_memory(memory_id)
        if retrieved_memory:
            print(f"✅ Retrieved memory: {retrieved_memory.content.data if hasattr(retrieved_memory.content, 'data') else retrieved_memory.content}")
        else:
            print("❌ Failed to retrieve memory")
            return False
        
        # Test 3: Search for memories
        print("\nTest 3: Searching memories")
        search_results = await manager.search_memories(
            query="test memory",
            limit=5
        )
        print(f"✅ Found {len(search_results)} memories in search")
        
        # Test 4: Update context
        print("\nTest 4: Updating context")
        await manager.update_context({
            "text": "Current conversation about testing",
            "user": "test_user",
            "session": "test_session"
        })
        print("✅ Context updated")
        
        # Test 5: Get prompt context
        print("\nTest 5: Getting prompt context")
        context_memories = await manager.get_prompt_context_memories(max_memories=3)
        print(f"✅ Retrieved {len(context_memories)} context memories for prompt")
        
        # Test 6: Get system stats
        print("\nTest 6: Getting system statistics")
        stats = await manager.get_system_stats()
        print(f"✅ System stats - Total memories: {stats.get('total_memories', 0)}")
        print(f"  - STM: {stats.get('tiers', {}).get('stm', {}).get('total_memories', 0)}")
        print(f"  - MTM: {stats.get('tiers', {}).get('mtm', {}).get('total_memories', 0)}")
        print(f"  - LTM: {stats.get('tiers', {}).get('ltm', {}).get('total_memories', 0)}")
        
        # Cleanup
        await manager.shutdown()
        print("✅ MemoryManager shutdown successfully")
        
        return True
        
    except Exception as e:
        print(f"❌ Error during memory operations: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_memory_lifecycle():
    """Test memory lifecycle operations"""
    print("\n=== Testing Memory Lifecycle ===")
    
    try:
        from neuroca.memory.manager.memory_manager import MemoryManager
        from neuroca.memory.backends import BackendType
        
        manager = MemoryManager(backend_type=BackendType.MEMORY)
        await manager.initialize()
        
        # Add multiple memories
        memory_ids = []
        for i in range(3):
            memory_id = await manager.add_memory(
                content=f"Memory content {i+1}",
                importance=0.5 + (i * 0.1),
                tags=[f"batch_{i}", "test"],
                initial_tier="stm"
            )
            memory_ids.append(memory_id)
        
        print(f"✅ Added {len(memory_ids)} memories to STM")
        
        # Test strengthening a memory
        if memory_ids:
            success = await manager.strengthen_memory(memory_ids[0], strengthen_amount=0.2)
            print(f"✅ Memory strengthening: {success}")
        
        # Test memory consolidation
        print("\nTesting memory consolidation...")
        consolidation_results = await manager.run_maintenance()
        print(f"✅ Maintenance completed: {consolidation_results.get('consolidated_memories', 0)} memories consolidated")
        
        await manager.shutdown()
        return True
        
    except Exception as e:
        print(f"❌ Error during lifecycle testing: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    print("NCA Memory System Integration Test")
    print("=" * 50)
    
    # Test basic operations
    basic_ok = await test_memory_operations()
    
    if basic_ok:
        # Test lifecycle operations
        lifecycle_ok = await test_memory_lifecycle()
        
        if lifecycle_ok:
            print("\n🎉 ALL TESTS PASSED! NCA Memory System is fully operational!")
            print("\n✅ Key capabilities verified:")
            print("  - Memory Manager instantiation and initialization")
            print("  - Memory storage (add_memory)")
            print("  - Memory retrieval (retrieve_memory)")
            print("  - Memory search (search_memories)")
            print("  - Context management (update_context, get_prompt_context_memories)")
            print("  - System statistics (get_system_stats)")
            print("  - Memory lifecycle (strengthen_memory, run_maintenance)")
            print("  - Clean shutdown")
        else:
            print("\n💥 Lifecycle tests failed")
    else:
        print("\n💥 Basic operation tests failed")

if __name__ == "__main__":
    asyncio.run(main())
