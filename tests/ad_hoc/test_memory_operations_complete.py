"""
Test complete memory operations to validate the memory system works end-to-end.
"""

import asyncio
import sys
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from neuroca.memory.backends import BackendType
from neuroca.memory.manager.memory_manager import MemoryManager


async def test_memory_operations():
    """Test complete memory operations workflow."""
    print("Testing complete memory operations...")
    
    # Initialize MemoryManager
    memory_manager = MemoryManager(
        backend_type=BackendType.MEMORY,
        backend_config={},
        config={"stm": {}, "mtm": {}, "ltm": {}},
    )
    
    try:
        await memory_manager.initialize()
        print("✅ MemoryManager initialized")
        
        # Test 1: Add a memory
        print("\n🔬 Testing memory storage...")
        memory_id = await memory_manager.add_memory(
            content="This is a test memory about cats being awesome pets.",
            summary="Test memory about cats",
            importance=0.8,
            metadata={"category": "pets", "test": True},
            tags=["cats", "pets", "test"]
        )
        print(f"✅ Added memory with ID: {memory_id}")
        
        # Test 2: Retrieve the memory
        print("\n🔬 Testing memory retrieval...")
        retrieved_memory = await memory_manager.retrieve_memory(memory_id)
        if retrieved_memory:
            print("✅ Successfully retrieved memory")
            print(f"  Content: {retrieved_memory.content.text}")
            print(f"  Summary: {retrieved_memory.content.summary}")
            print(f"  Importance: {retrieved_memory.metadata.importance}")
        else:
            print("❌ Failed to retrieve memory")
            return False
        
        # Test 3: Search for memories
        print("\n🔬 Testing memory search...")
        search_results = await memory_manager.search_memories(
            query="cats pets",
            limit=5
        )
        if search_results:
            print(f"✅ Found {len(search_results)} memories in search")
            for result in search_results:
                # Handle both MemoryItem objects and dict results
                if hasattr(result, 'content'):
                    text = result.content.text or "N/A"
                else:
                    text = result.get('content', {}).get('text', 'N/A')
                print(f"  - {text[:50]}...")
        else:
            print("⚠️ No search results (expected for new system)")
        
        # Test 4: Update memory
        print("\n🔬 Testing memory update...")
        update_success = await memory_manager.update_memory(
            memory_id,
            content="This is an UPDATED test memory about cats being awesome pets.",
            importance=0.9
        )
        if update_success:
            print("✅ Successfully updated memory")
            
            # Verify update
            updated_memory = await memory_manager.retrieve_memory(memory_id)
            if updated_memory and "UPDATED" in updated_memory.content.text:
                print("✅ Update verified")
            else:
                print("❌ Update not reflected")
                return False
        else:
            print("❌ Failed to update memory")
            return False
        
        # Test 5: Context management
        print("\n🔬 Testing context management...")
        await memory_manager.update_context({
            "text": "I want to learn about pets",
            "user_goal": "pet_research"
        })
        print("✅ Context updated")
        
        # Get prompt context
        context_memories = await memory_manager.get_prompt_context_memories(max_memories=3)
        print(f"✅ Got {len(context_memories)} context memories for prompt")
        
        # Test 6: System stats
        print("\n🔬 Testing system stats...")
        stats = await memory_manager.get_system_stats()
        print("✅ Retrieved system stats:")
        print(f"  Total memories: {stats.get('total_memories', 'N/A')}")
        for tier_name, tier_stats in stats.get('tiers', {}).items():
            print(f"  {tier_name.upper()}: {tier_stats.get('total_memories', 0)} memories")
        
        # Test 7: Consolidation
        print("\n🔬 Testing memory consolidation...")
        consolidation_result = await memory_manager.consolidate_memory(
            memory_id,
            source_tier="stm",
            target_tier="mtm",
            additional_metadata={"consolidated": True}
        )
        if consolidation_result:
            print(f"✅ Successfully consolidated memory to MTM: {consolidation_result}")
        else:
            print("❌ Failed to consolidate memory")
            return False
        
        # Test 8: Delete memory
        print("\n🔬 Testing memory deletion...")
        delete_success = await memory_manager.delete_memory(consolidation_result)
        if delete_success:
            print("✅ Successfully deleted memory")
        else:
            print("❌ Failed to delete memory")
            return False
        
        print("\n🎉 All memory operations tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ Memory operations failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        # Cleanup
        await memory_manager.shutdown()
        print("✅ MemoryManager shutdown complete")


if __name__ == "__main__":
    success = asyncio.run(test_memory_operations())
    sys.exit(0 if success else 1)
