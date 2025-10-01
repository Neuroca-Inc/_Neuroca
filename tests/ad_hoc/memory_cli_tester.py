#!/usr/bin/env python3
"""
NeuroCa Memory System CLI Tester

A simple command-line interface for testing and debugging the NCA memory system.
This provides direct access to memory operations without external dependencies.

Usage:
    python memory_cli_tester.py
"""

import asyncio
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Import the NCA memory system
try:
    from neuroca.memory.manager.memory_manager import MemoryManager
    from neuroca.memory.backends import BackendType
    print("✓ Successfully imported NCA MemoryManager")
except ImportError as e:
    print(f"❌ Failed to import NCA components: {e}")
    sys.exit(1)


class MemoryCLI:
    """Simple CLI interface for testing the NCA memory system."""
    
    def __init__(self):
        self.memory_manager: Optional[MemoryManager] = None
        self.running = True
        
    async def initialize(self):
        """Initialize the memory manager."""
        try:
            print("🔧 Initializing NCA Memory System...")
            self.memory_manager = MemoryManager(
                backend_type=BackendType.MEMORY,  # Using in-memory backend
                working_buffer_size=10
            )
            await self.memory_manager.initialize()
            print("✅ Memory system initialized successfully!")
            return True
        except Exception as e:
            print(f"❌ Failed to initialize memory system: {e}")
            return False
    
    async def shutdown(self):
        """Shutdown the memory manager."""
        if self.memory_manager:
            try:
                await self.memory_manager.shutdown()
                print("✅ Memory system shutdown successfully")
            except Exception as e:
                print(f"⚠️ Error during shutdown: {e}")
    
    def print_help(self):
        """Print available commands."""
        help_text = """
📋 NeuroCa Memory System CLI Commands:
─────────────────────────────────────────────────────────
add <text>           - Add memory to system
get <memory_id>      - Retrieve specific memory by ID  
search <query>       - Search for memories containing text
list                 - List recent memories
context <text>       - Update current context (triggers memory retrieval)
prompt               - Get prompt context memories
clear                - Clear current context
chat <message>       - Chat with NCA (with memory integration)
demo                 - Run a demo conversation showing memory features
stats                - Show system statistics (if working)
help                 - Show this help
exit/quit            - Exit the CLI
─────────────────────────────────────────────────────────
"""
        print(help_text)
    
    async def add_memory(self, content: str):
        """Add a memory to the system."""
        try:
            memory_id = await self.memory_manager.add_memory(
                content=content,
                importance=0.6,
                tags=["cli_test"],
                metadata={"source": "cli", "timestamp": datetime.now().isoformat()}
            )
            print(f"✅ Added memory: {memory_id}")
            return memory_id
        except Exception as e:
            print(f"❌ Failed to add memory: {e}")
            return None
    
    async def get_memory(self, memory_id: str):
        """Retrieve a specific memory."""
        try:
            memory = await self.memory_manager.retrieve_memory(memory_id)
            if memory:
                print(f"✅ Retrieved memory {memory_id}:")
                # Pretty print the memory content
                content = memory.get('content', {})
                text = content.get('text', '[No text content]')
                metadata = memory.get('metadata', {})
                created = metadata.get('created_at', 'Unknown')
                print(f"   Text: {text}")
                print(f"   Created: {created}")
                print(f"   Importance: {metadata.get('importance', 'N/A')}")
            else:
                print(f"❌ Memory {memory_id} not found")
        except Exception as e:
            print(f"❌ Failed to retrieve memory: {e}")
    
    async def search_memories(self, query: str):
        """Search for memories."""
        try:
            results = await self.memory_manager.search_memories(
                query=query,
                limit=5
            )
            print(f"🔍 Found {len(results)} memories for '{query}':")
            for i, memory in enumerate(results, 1):
                content = memory.get('content', {})
                text = content.get('text', '[No text]')
                relevance = memory.get('_relevance', 'N/A')
                tier = memory.get('tier', 'Unknown')
                print(f"   {i}. [{tier}] {text[:50]}... (relevance: {relevance})")
        except Exception as e:
            print(f"❌ Search failed: {e}")
    
    async def list_memories(self):
        """List recent memories (simplified version using search)."""
        try:
            # Get all memories by searching with empty query
            results = await self.memory_manager.search_memories(
                query="",
                limit=10
            )
            print(f"📋 Recent memories ({len(results)} found):")
            for i, memory in enumerate(results, 1):
                memory_id = memory.get('id', 'Unknown')
                content = memory.get('content', {})
                text = content.get('text', '[No text]')
                tier = memory.get('tier', 'Unknown')
                print(f"   {i}. [{tier}] {memory_id[:8]}... {text[:40]}...")
        except Exception as e:
            print(f"❌ Failed to list memories: {e}")
    
    async def update_context(self, context_text: str):
        """Update the current context."""
        try:
            await self.memory_manager.update_context({
                "text": context_text,
                "timestamp": datetime.now().isoformat(),
                "source": "cli"
            })
            print(f"✅ Context updated: '{context_text}'")
            print("🧠 Relevant memories retrieved for working memory")
        except Exception as e:
            print(f"❌ Failed to update context: {e}")
    
    async def get_prompt_context(self):
        """Get prompt context memories."""
        try:
            memories = await self.memory_manager.get_prompt_context_memories(
                max_memories=5
            )
            print(f"🎯 Prompt context memories ({len(memories)} items):")
            for i, memory in enumerate(memories, 1):
                content = memory.get('content', '[No content]')
                relevance = memory.get('relevance', 'N/A')
                tier = memory.get('tier', 'Unknown')
                print(f"   {i}. [{tier}] {content[:50]}... (relevance: {relevance})")
        except Exception as e:
            print(f"❌ Failed to get prompt context: {e}")
    
    async def clear_context(self):
        """Clear the current context."""
        try:
            await self.memory_manager.clear_context()
            print("✅ Context cleared")
        except Exception as e:
            print(f"❌ Failed to clear context: {e}")
    
    async def show_stats(self):
        """Show system statistics."""
        try:
            stats = await self.memory_manager.get_system_stats()
            print("📊 System Statistics:")
            print(f"   Total memories: {stats.get('total_memories', 'Unknown')}")
            tiers = stats.get('tiers', {})
            for tier_name, tier_stats in tiers.items():
                print(f"   {tier_name.upper()}: {tier_stats}")
        except Exception as e:
            print(f"❌ Failed to get stats (known issue): {e}")
    
    async def chat_with_nca(self, message: str):
        """Simulate a chat conversation with NCA memory integration."""
        print(f"💬 You: {message}")
        print("🧠 NCA: Processing with memory integration...")
        
        try:
            # Step 1: Update context with the user's message
            await self.memory_manager.update_context({
                "text": message,
                "type": "user_message",
                "timestamp": datetime.now().isoformat()
            })
            
            # Step 2: Get relevant memories for context
            context_memories = await self.memory_manager.get_prompt_context_memories(max_memories=3)
            
            # Step 3: Simulate AI processing with memory context
            print("📚 Using relevant memories:")
            for i, memory in enumerate(context_memories, 1):
                content = memory.get('content', '[No content]')
                print(f"   {i}. {content[:60]}...")
            
            # Step 4: Generate simulated response based on context
            if context_memories:
                response = f"Based on our previous conversations, I remember we discussed {len(context_memories)} related topics. "
                response += "Here's my response incorporating that context: "
                response += f"I understand you're asking about '{message}'. "
                response += "Let me provide a contextual response based on our history."
            else:
                response = "This seems to be a new topic for us. I'll remember this conversation. "
                response += f"Regarding '{message}', let me help you with that."
            
            print(f"🤖 NCA: {response}")
            
            # Step 5: Store this interaction as a memory
            memory_content = f"User asked: {message} | AI responded: {response[:100]}..."
            memory_id = await self.memory_manager.add_memory(
                content=memory_content,
                importance=0.7,
                tags=["conversation", "chat"],
                metadata={
                    "type": "chat_interaction",
                    "user_message": message,
                    "ai_response": response,
                    "timestamp": datetime.now().isoformat()
                }
            )
            print(f"💾 Stored conversation as memory: {memory_id[:8]}...")
            
        except Exception as e:
            print(f"❌ Chat processing failed: {e}")
    
    async def run_demo(self):
        """Run a demonstration of NCA memory features."""
        print("🎭 Starting NCA Memory Demonstration...")
        print("=" * 50)
        
        try:
            # Demo conversation sequence
            demo_messages = [
                "I'm working on a Python project",
                "What are some good practices for memory management?",
                "How do neural networks work?", 
                "Can you remind me what we discussed about Python?",
                "What's the difference between STM and LTM?"
            ]
            
            for i, message in enumerate(demo_messages, 1):
                print(f"\n--- Demo Step {i} ---")
                await self.chat_with_nca(message)
                
                # Show working memory state
                print("\n🧠 Current working memory:")
                await self.get_prompt_context()
                
                # Brief pause for readability
                await asyncio.sleep(1)
            
            print("\n🎯 Demo complete! The system has learned from our conversation.")
            print("Try 'search Python' or 'search memory' to see what it remembered!")
            
        except Exception as e:
            print(f"❌ Demo failed: {e}")
    
    async def run(self):
        """Run the interactive CLI."""
        print("🧠 NeuroCognitive Architecture (NCA) Memory CLI Tester")
        print("=" * 60)
        
        # Initialize the system
        if not await self.initialize():
            return
        
        self.print_help()
        
        try:
            while self.running:
                try:
                    # Get user input
                    user_input = input("\n🧠 nca> ").strip()
                    
                    if not user_input:
                        continue
                    
                    # Parse command
                    parts = user_input.split(' ', 1)
                    command = parts[0].lower()
                    args = parts[1] if len(parts) > 1 else ""
                    
                    # Execute command
                    if command in ['exit', 'quit']:
                        self.running = False
                        break
                    elif command == 'help':
                        self.print_help()
                    elif command == 'add':
                        if args:
                            await self.add_memory(args)
                        else:
                            print("❌ Usage: add <text>")
                    elif command == 'get':
                        if args:
                            await self.get_memory(args)
                        else:
                            print("❌ Usage: get <memory_id>")
                    elif command == 'search':
                        if args:
                            await self.search_memories(args)
                        else:
                            print("❌ Usage: search <query>")
                    elif command == 'list':
                        await self.list_memories()
                    elif command == 'context':
                        if args:
                            await self.update_context(args)
                        else:
                            print("❌ Usage: context <text>")
                    elif command == 'prompt':
                        await self.get_prompt_context()
                    elif command == 'clear':
                        await self.clear_context()
                    elif command == 'chat':
                        if args:
                            await self.chat_with_nca(args)
                        else:
                            print("❌ Usage: chat <message>")
                    elif command == 'demo':
                        await self.run_demo()
                    elif command == 'stats':
                        await self.show_stats()
                    else:
                        print(f"❌ Unknown command: {command}. Type 'help' for available commands.")
                        
                except KeyboardInterrupt:
                    print("\n\n⚠️ Interrupted by user")
                    self.running = False
                    break
                except Exception as e:
                    print(f"❌ Command error: {e}")
                    
        finally:
            print("\n🔄 Shutting down...")
            await self.shutdown()
            print("👋 Goodbye!")


async def main():
    """Main entry point."""
    cli = MemoryCLI()
    await cli.run()


if __name__ == "__main__":
    # Run the CLI
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"💥 Fatal error: {e}")
        sys.exit(1)
