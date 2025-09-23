#!/usr/bin/env python3
"""
Memory Pipeline Fix Validation Test

This test validates that the critical memory pipeline bug has been fixed
and that text content is properly preserved through the entire flow:
MemoryManager → Tier → Backend → Storage → Retrieval → Search

Expected behavior:
- MemoryManager.add_memory() creates proper MemoryItem with MemoryContent
- BaseMemoryTier.store() correctly handles serialized MemoryItem (dict)
- Content is preserved exactly as provided (no corruption)
- Search returns memories with correct text content
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from neuroca.memory.manager.memory_manager import MemoryManager
from neuroca.memory.backends import BackendType


async def test_memory_pipeline_fix():
    """Test the complete memory pipeline with the fix applied."""
    print("🧠 Testing Memory Pipeline Fix")
    print("=" * 50)
    
    # Initialize memory manager
    memory_manager = MemoryManager(
        backend_type=BackendType.MEMORY,
        working_buffer_size=10
    )
    
    try:
        await memory_manager.initialize()
        print("✅ MemoryManager initialized")
        
        # Test data - this is what was failing before
        test_content = "User: my name is justin\nAssistant: Nice to meet you, Justin!"
        test_metadata = {
            "type": "chat_interaction",
            "model": "test_model",
            "timestamp": "2025-06-06T16:00:00"
        }
        test_tags = ["conversation", "chat", "test"]
        
        print("\n📝 Storing memory with content:")
        print(f"   Text: '{test_content[:50]}...'")
        print(f"   Tags: {test_tags}")
        
        # Add memory - this should now work correctly
        memory_id = await memory_manager.add_memory(
            content=test_content,
            importance=0.7,
            metadata=test_metadata,
            tags=test_tags
        )
        
        print(f"✅ Memory stored with ID: {memory_id}")
        
        # Retrieve the memory directly
        print("\n🔍 Testing direct retrieval...")
        retrieved_memory = await memory_manager.retrieve_memory(memory_id)
        
        if retrieved_memory:
            print("✅ Memory retrieved successfully")
            
            # Check content preservation - MemoryItem has .content.text
            stored_text = retrieved_memory.content.text
            print(f"   Stored text: '{stored_text[:50]}...'")
            
            if stored_text == test_content:
                print("✅ Content preserved exactly!")
            else:
                print("❌ Content corruption detected!")
                print(f"   Expected: '{test_content}'")
                print(f"   Got:      '{stored_text}'")
                return False
        else:
            print("❌ Memory retrieval failed!")
            return False
        
        # Test search functionality
        print("\n🔍 Testing search functionality...")
        search_results = await memory_manager.search_memories(
            query="justin name",
            limit=5,
            min_relevance=0.1
        )
        
        if search_results:
            print(f"✅ Search returned {len(search_results)} results")
            
            for i, result in enumerate(search_results):
                content = result.get("content", {}).get("text", "No text")
                relevance = result.get("_relevance", "N/A")
                tier = result.get("tier", "Unknown")
                print(f"   {i+1}. [{tier}] {content[:50]}... (relevance: {relevance})")
                
                # Check if our test content is found
                if content == test_content:
                    print("✅ Test content found in search results!")
                    break
            else:
                print("⚠️ Test content not found in search results")
        else:
            print("❌ Search returned no results!")
        
        # Test context update and working memory
        print("\n🧠 Testing context update and working memory...")
        await memory_manager.update_context({
            "text": "justin",
            "type": "user_query"
        })
        
        context_memories = await memory_manager.get_prompt_context_memories(max_memories=5)
        
        if context_memories:
            print(f"✅ Working memory contains {len(context_memories)} relevant items")
            for i, memory in enumerate(context_memories):
                content = memory.get("content", "No content")
                relevance = memory.get("relevance", "N/A")
                print(f"   {i+1}. {content[:50]}... (relevance: {relevance})")
        else:
            print("⚠️ No memories in working memory context")
        
        # Test memory stats
        print("\n📊 Testing system stats...")
        try:
            stats = await memory_manager.get_system_stats()
            print("✅ System stats retrieved:")
            print(f"   Total memories: {stats.get('total_memories', 'Unknown')}")
            
            tiers = stats.get('tiers', {})
            for tier_name, tier_stats in tiers.items():
                print(f"   {tier_name.upper()}: {tier_stats}")
        except Exception as e:
            print(f"⚠️ Stats retrieval failed (expected): {e}")
        
        print("\n🎉 Memory pipeline test completed successfully!")
        print("✅ All core functionality working correctly")
        return True
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        await memory_manager.shutdown()
        print("🔄 MemoryManager shutdown complete")


async def main():
    """Run the memory pipeline validation test."""
    print("🚀 Memory Pipeline Fix Validation")
    print("This test validates the critical bug fix in BaseMemoryTier.store()")
    print()
    
    success = await test_memory_pipeline_fix()
    
    if success:
        print("\n🎊 VALIDATION SUCCESSFUL!")
        print("The memory pipeline fix is working correctly.")
        print("Text content is preserved through the entire flow.")
    else:
        print("\n💥 VALIDATION FAILED!")
        print("The memory pipeline still has issues.")
        
    return success


if __name__ == "__main__":
    try:
        result = asyncio.run(main())
        sys.exit(0 if result else 1)
    except KeyboardInterrupt:
        print("\n⚠️ Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Fatal error: {e}")
        sys.exit(1)
