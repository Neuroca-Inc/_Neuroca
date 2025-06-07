#!/usr/bin/env python3
"""
NeuroCa Chat Interface with Real LLM Integration

A complete chat interface that integrates NeuroCa's memory system with Ollama LLMs.
Demonstrates the full power of bio-inspired memory + local AI models.
Automatically starts Ollama if not running.

Usage:
    python nca_chat_with_llm.py
"""

import asyncio
import logging
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Import the NCA components
try:
    from neuroca.memory.manager.memory_manager import MemoryManager
    from neuroca.memory.backends import BackendType
    from neuroca.integration.manager import LLMIntegrationManager
    from neuroca.integration.adapters.ollama import OllamaAdapter
    from neuroca.integration.models import LLMRequest
    print("✓ Successfully imported NCA components")
except ImportError as e:
    print(f"❌ Failed to import NCA components: {e}")
    sys.exit(1)


class NCAChat:
    """Complete NCA chat interface with memory-enhanced LLM conversations."""
    
    def __init__(self, model_name: str = "gemma2:2b"):
        self.model_name = model_name
        self.memory_manager: Optional[MemoryManager] = None
        self.llm_manager: Optional[LLMIntegrationManager] = None
        self.running = True
        self.conversation_history = []
        
    def _check_ollama_running(self) -> bool:
        """Check if Ollama is running on localhost:11434."""
        try:
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            result = sock.connect_ex(('localhost', 11434))
            sock.close()
            return result == 0
        except Exception:
            return False
    
    def _start_ollama(self) -> bool:
        """Start Ollama service."""
        try:
            print("🚀 Starting Ollama service...")
            # Try to start Ollama
            subprocess.Popen(['ollama', 'serve'], 
                           stdout=subprocess.DEVNULL, 
                           stderr=subprocess.DEVNULL)
            
            # Wait for startup
            for i in range(30):  # Wait up to 30 seconds
                if self._check_ollama_running():
                    print("✅ Ollama service started successfully")
                    return True
                time.sleep(1)
                if i % 5 == 0:
                    print(f"⏳ Waiting for Ollama to start... ({i+1}/30)")
            
            print("❌ Timed out waiting for Ollama to start")
            return False
            
        except FileNotFoundError:
            print("❌ Ollama not found. Please install Ollama first:")
            print("   https://ollama.com/download")
            return False
        except Exception as e:
            print(f"❌ Failed to start Ollama: {e}")
            return False
        
    async def initialize(self):
        """Initialize both memory and LLM systems."""
        try:
            print("🔧 Initializing NCA Systems...")
            
            # Check if Ollama is running, start if not
            if not self._check_ollama_running():
                print("⚠️ Ollama service not detected")
                if not self._start_ollama():
                    return False
            else:
                print("✅ Ollama service is running")
            
            # Initialize Memory Manager
            print("📚 Starting memory system...")
            self.memory_manager = MemoryManager(
                backend_type=BackendType.MEMORY,
                working_buffer_size=10
            )
            await self.memory_manager.initialize()
            print("✅ Memory system ready")
            
            # Initialize LLM Integration Manager
            print(f"🤖 Connecting to Ollama model: {self.model_name}...")
            
            # Configure Ollama adapter
            ollama_config = {
                "base_url": "http://localhost:11434",
                "default_model": self.model_name,
                "request_timeout": 120
            }
            
            # Create and register Ollama adapter
            ollama_adapter = OllamaAdapter(ollama_config)
            
            # Create LLM Integration Manager with proper config
            llm_config = {
                "default_provider": "ollama",
                "default_model": self.model_name,
                "providers": {
                    "ollama": ollama_config
                },
                "store_interactions": True
            }
            
            self.llm_manager = LLMIntegrationManager(
                config=llm_config,
                memory_manager=self.memory_manager
            )
            
            # Register the Ollama adapter manually since it's not auto-initialized
            self.llm_manager.adapters["ollama"] = ollama_adapter
            
            # Test connection and get available models
            try:
                available_models = await ollama_adapter.get_available_models()
                if self.model_name not in available_models:
                    print(f"⚠️ Model {self.model_name} not found in available models:")
                    print(f"   Available: {available_models}")
                    if available_models:
                        self.model_name = available_models[0]
                        print(f"   Using {self.model_name} instead")
                    else:
                        print("❌ No models available. Installing recommended model...")
                        subprocess.run(['ollama', 'pull', 'gemma2:2b'], check=True)
                        self.model_name = 'gemma2:2b'
                        print(f"✅ Installed and using {self.model_name}")
                
                print(f"✅ Connected to {self.model_name}")
                return True
                
            except Exception as model_error:
                print(f"❌ Failed to connect to model: {model_error}")
                print("💡 Try installing a model first:")
                print(f"   ollama pull {self.model_name}")
                return False
            
        except Exception as e:
            print(f"❌ Initialization failed: {e}")
            return False
    
    async def shutdown(self):
        """Shutdown all systems."""
        print("\n🔄 Shutting down systems...")
        
        if self.llm_manager:
            try:
                await self.llm_manager.close()
                print("✅ LLM manager shutdown")
            except Exception as e:
                print(f"⚠️ LLM shutdown error: {e}")
                
        if self.memory_manager:
            try:
                await self.memory_manager.shutdown()
                print("✅ Memory system shutdown")
            except Exception as e:
                print(f"⚠️ Memory shutdown error: {e}")
    
    def print_welcome(self):
        """Print welcome message and instructions."""
        welcome = f"""
🧠 NeuroCognitive Architecture (NCA) + {self.model_name.upper()}
═══════════════════════════════════════════════════════════════════

🌟 WHAT MAKES THIS SPECIAL:
• Bio-inspired multi-tiered memory (STM/MTM/LTM)
• Context-aware conversations with memory injection
• Local AI with NO data leaving your computer
• Memory consolidation and retrieval like human cognition
• Automatic Ollama service management

💬 CHAT COMMANDS:
• Just type your message and press Enter
• Type 'memory' to see what I remember about our conversation
• Type 'context' to see my current working memory
• Type 'clear' to clear conversation history
• Type 'stats' to see memory system statistics
• Type 'help' for this message
• Type 'exit' or 'quit' to end

🚀 Ready to experience memory-enhanced AI conversation!
═══════════════════════════════════════════════════════════════════
"""
        print(welcome)
    
    async def process_message(self, user_message: str) -> str:
        """Process a user message through the full NCA pipeline."""
        try:
            # Update context with user message (triggers memory retrieval)
            await self.memory_manager.update_context({
                "text": user_message,
                "type": "user_message",
                "timestamp": datetime.now().isoformat()
            })
            
            # Get relevant memories for context using search
            context_memories = []
            try:
                search_results = await self.memory_manager.search_memories(
                    query=user_message,
                    limit=3,
                    min_relevance=0.3
                )
                
                # Convert search results to format expected by prompt builder
                for result in search_results:
                    context_memories.append({
                        'content': result.get('content', {}).get('text', 'No content'),
                        'relevance': result.get('_relevance', 0.5),
                        'tier': result.get('tier', 'unknown')
                    })
            except Exception as e:
                logger.warning(f"Failed to retrieve context memories: {e}")
                # Continue without context memories
            
            # Build enhanced prompt with memory context
            system_prompt = "You are a helpful AI assistant with access to conversation memory. "
            system_prompt += "Use the provided memory context to give more informed responses."
            
            if context_memories:
                memory_context = "\n".join([
                    f"Memory: {mem.get('content', 'No content')}"
                    for mem in context_memories
                ])
                system_prompt += f"\n\nRelevant memories:\n{memory_context}"
            
            # Add conversation history
            messages = [{"role": "system", "content": system_prompt}]
            
            # Add recent conversation history (last 6 messages)
            recent_history = self.conversation_history[-6:] if len(self.conversation_history) > 6 else self.conversation_history
            messages.extend(recent_history)
            
            # Add current message
            messages.append({"role": "user", "content": user_message})
            
            # Generate response using LLM with memory integration
            print("🧠 Processing with memory integration...")
            
            response = await self.llm_manager.query(
                prompt=user_message,
                provider="ollama",
                model=self.model_name,
                max_tokens=1000,
                temperature=0.7,
                memory_context=True,
                health_aware=False,
                goal_directed=False
            )
            
            ai_response = response.content
            
            # Store this interaction in memory
            interaction_content = f"User: {user_message}\nAssistant: {ai_response}"
            try:
                memory_id = await self.memory_manager.add_memory(
                    content=interaction_content,
                    importance=0.7,
                    tags=["conversation", "chat", "ollama"],
                    metadata={
                        "type": "chat_interaction",
                        "model": self.model_name,
                        "user_message": user_message,
                        "ai_response": ai_response,
                        "timestamp": datetime.now().isoformat()
                    }
                )
                print(f"🧠 Stored memory with ID: {memory_id}")
                
                # Verify it was stored by immediately searching for it
                verification = await self.memory_manager.search_memories(
                    query=user_message,
                    limit=1
                )
                print(f"🔍 Verification search found {len(verification)} memories")
                
            except Exception as e:
                print(f"❌ Failed to store memory: {e}")
            
            # Update conversation history
            self.conversation_history.append({"role": "user", "content": user_message})
            self.conversation_history.append({"role": "assistant", "content": ai_response})
            
            return ai_response
            
        except Exception as e:
            error_msg = f"Error processing message: {str(e)}"
            print(f"❌ {error_msg}")
            return "I apologize, but I encountered an error processing your message. Please try again."
    
    async def show_memory_summary(self):
        """Show what the system remembers about the conversation."""
        try:
            # Search for conversation memories
            results = await self.memory_manager.search_memories(
                query="conversation chat user assistant",
                limit=5
            )
            
            print("\n🧠 MEMORY SUMMARY:")
            print("=" * 40)
            
            if results:
                for i, memory in enumerate(results, 1):
                    content = memory.get('content', 'No content')
                    tier = memory.get('tier', 'Unknown')
                    relevance = memory.get('_relevance', 'N/A')
                    
                    # Truncate content for display
                    if len(content) > 100:
                        content = content[:97] + "..."
                    
                    print(f"{i}. [{tier}] {content} (relevance: {relevance})")
            else:
                print("No conversation memories found yet.")
            print("=" * 40)
            
        except Exception as e:
            print(f"❌ Error retrieving memories: {e}")
    
    async def show_context(self):
        """Show current working memory context."""
        try:
            context_memories = await self.memory_manager.get_prompt_context_memories(
                max_memories=5
            )
            
            print("\n🎯 CURRENT WORKING MEMORY:")
            print("=" * 40)
            
            if context_memories:
                for i, memory in enumerate(context_memories, 1):
                    content = memory.get('content', 'No content')
                    relevance = memory.get('relevance', 'N/A')
                    
                    if len(content) > 80:
                        content = content[:77] + "..."
                    
                    print(f"{i}. {content} (relevance: {relevance})")
            else:
                print("No items in working memory.")
            print("=" * 40)
            
        except Exception as e:
            print(f"❌ Error retrieving context: {e}")
    
    async def clear_conversation(self):
        """Clear conversation history and context."""
        try:
            await self.memory_manager.clear_context()
            self.conversation_history = []
            print("✅ Conversation history and context cleared")
        except Exception as e:
            print(f"❌ Error clearing conversation: {e}")
    
    async def show_stats(self):
        """Show memory system statistics."""
        try:
            stats = await self.memory_manager.get_system_stats()
            
            print("\n📊 MEMORY SYSTEM STATISTICS:")
            print("=" * 40)
            print(f"Total memories: {stats.get('total_memories', 'Unknown')}")
            
            tiers = stats.get('tiers', {})
            for tier_name, tier_stats in tiers.items():
                print(f"{tier_name.upper()}: {tier_stats}")
            print("=" * 40)
            
        except Exception as e:
            print(f"❌ Stats unavailable (known issue): {str(e)}")
    
    async def run(self):
        """Run the interactive chat interface."""
        print("🧠 NeuroCognitive Architecture (NCA) Chat Interface")
        print("=" * 60)
        
        # Initialize systems
        if not await self.initialize():
            return
        
        self.print_welcome()
        
        try:
            while self.running:
                try:
                    # Get user input
                    user_input = input(f"\n💬 You: ").strip()
                    
                    if not user_input:
                        continue
                    
                    # Handle special commands
                    if user_input.lower() in ['exit', 'quit']:
                        self.running = False
                        break
                    elif user_input.lower() == 'help':
                        self.print_welcome()
                        continue
                    elif user_input.lower() == 'memory':
                        await self.show_memory_summary()
                        continue
                    elif user_input.lower() == 'context':
                        await self.show_context()
                        continue
                    elif user_input.lower() == 'clear':
                        await self.clear_conversation()
                        continue
                    elif user_input.lower() == 'stats':
                        await self.show_stats()
                        continue
                    
                    # Process the message through NCA + LLM
                    response = await self.process_message(user_input)
                    print(f"\n🤖 {self.model_name}: {response}")
                    
                except KeyboardInterrupt:
                    print("\n\n⚠️ Interrupted by user")
                    self.running = False
                    break
                except Exception as e:
                    print(f"❌ Error: {e}")
                    
        finally:
            await self.shutdown()
            print("👋 Goodbye!")


async def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="NCA Chat with Ollama")
    parser.add_argument("--model", default="gemma2:2b", 
                       help="Ollama model to use (default: gemma2:2b)")
    
    args = parser.parse_args()
    
    # Accept whatever model the user specifies
    print(f"🎯 Targeting model: {args.model}")
    
    chat = NCAChat(model_name=args.model)
    await chat.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"💥 Fatal error: {e}")
        sys.exit(1)
