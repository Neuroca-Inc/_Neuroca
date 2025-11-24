#!/usr/bin/env python3
"""
Test script for the Neuroca memory system with LLM integration.

This script demonstrates how to use the memory system to create a conversational agent
that can remember previous interactions and use those memories in context.
"""

# ruff: noqa: E402

import asyncio
import os
import argparse
import json
import sys
import time
import uuid
from pathlib import Path
from typing import List

# Ensure repository sources are importable when running directly from the repo root.
ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from neuroca.memory.backends import BackendType
from neuroca.memory.manager import MemoryManager
from neuroca.memory.models.memory_item import MemoryItem
from neuroca.memory.models.search import MemorySearchResult

# Uncomment to use OpenAI API. Add your API key to .env first.
try:
    from dotenv import load_dotenv
    from openai import OpenAI
except ImportError:
    load_dotenv = None  # type: ignore[assignment]
    OpenAI = None  # type: ignore[assignment]
    print("OpenAI package not available. Install with: pip install openai python-dotenv")
    OPENAI_AVAILABLE = False
else:
    OPENAI_AVAILABLE = True

# Optional local LLM fallback (Ollama)
try:
    import ollama  # type: ignore
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False
class ConversationalAgent:
    """A simple conversational agent that uses the memory system to remember context."""
    
    def __init__(self, use_sqlite: bool = False, fast_tiers: bool = False, history_window: int | None = None):
        """Initialize the agent with memory system."""
        self.conversation_history = []
        self.memory_manager = None
        self.backend_type = BackendType.SQLITE if use_sqlite else BackendType.MEMORY
        self.conversation_id = str(uuid.uuid4())
        self.fast_tiers = fast_tiers or os.getenv("FAST_TIERS", "").strip().lower() in ("1", "true", "yes")
        try:
            self.history_window = int(history_window) if history_window is not None else None
        except Exception:
            self.history_window = None
        
        # OpenAI setup if available
        self._openai_client = None
        if OPENAI_AVAILABLE and load_dotenv:
            load_dotenv()
            api_key = os.getenv("OPENAI_API_KEY")
            if OpenAI and api_key:
                try:
                    self._openai_client = OpenAI(api_key=api_key)
                except Exception:
                    self._openai_client = None
            else:
                self._openai_client = None
            if not api_key:
                print("Warning: OPENAI_API_KEY not found in .env file")

        # Runtime provider controls
        # provider: openai | ollama | none (auto-selected by availability)
        if OPENAI_AVAILABLE and self._openai_client:
            self.provider = "openai"
        elif 'OLLAMA_AVAILABLE' in globals() and OLLAMA_AVAILABLE:
            self.provider = "ollama"
        else:
            self.provider = "none"

        self.use_llm = True  # toggle during interactive runs
        self.openai_model = os.getenv("OPENAI_MODEL", "gpt-5")
        self.ollama_model = os.getenv("OLLAMA_MODEL", "gemma3:4b")
        self.scope = os.getenv("MEMORY_SCOPE", "all").strip().lower()
        self.use_full_memory = (self.scope == "all")

        # Prefer Responses API for newer models unless explicitly overridden
        self.prefer_responses = os.getenv("OPENAI_USE_RESPONSES", "").strip().lower() in ("1", "true", "yes")
        if self.provider == "openai":
            m = (self.openai_model or "").lower()
            # Heuristic: models like gpt-5, gpt-4o, gpt-4.1, o3, o4 tend to require Responses API or different params
            if any(key in m for key in ("gpt-5", "gpt-4o", "gpt-4.1", "o3", "o4")):
                self.prefer_responses = True or self.prefer_responses
    
    async def initialize(self):
        """Initialize the memory system."""
        print(f"Initializing memory system with {self.backend_type} backend...")
        # Base config
        config = {
            "stm": {"default_ttl": 3600},  # 1 hour TTL
            "mtm": {"max_capacity": 1000},
            "ltm": {"maintenance_interval": 86400},  # 24 hours
            "monitoring": {"metrics": {"enabled": False}, "events": {"enabled": False}},
        }
        # Fast tier mode to exercise STM -> MTM -> LTM promotions during a short demo
        if self.fast_tiers:
            config["stm"]["default_ttl"] = 15
            # Small capacity to force promotion pressure
            config["mtm"].update({"max_capacity": 20, "consolidation_interval": 5})
            # Frequent LTM maintenance
            config["ltm"].update({"maintenance_interval": 10})

        self.memory_manager = MemoryManager(
            config=config,
            mtm_storage_type=self.backend_type,
            ltm_storage_type=self.backend_type,
            vector_storage_type=BackendType.MEMORY  # Use in-memory for vector storage
        )
        
        await self.memory_manager.initialize()
        print("Memory system initialized successfully!")
    
    async def shutdown(self):
        """Shutdown the memory system."""
        if self.memory_manager:
            print("Shutting down memory system...")
            await self.memory_manager.shutdown()
            print("Memory system shut down successfully!")
    
    async def store_memory(self, content: str, source: str, importance: float = 0.7):
        """Store a new memory in the system."""
        memory_id = await self.memory_manager.add_memory(
            content=content,
            summary=f"From {source}: {content[:30]}...",
            importance=importance,
            tags=[source, "conversation"],
            metadata={
                "conversation_id": self.conversation_id,
                "timestamp": time.time(),
                "source": source
            },
            initial_tier="stm"  # Start in short-term memory
        )
        
        print(f"Added memory with ID: {memory_id}")
        return memory_id

    # Corrected indentation for this method
    async def retrieve_relevant_memories(self, query: str, limit: int = 5) -> List[MemorySearchResult]:
        """Retrieve memories relevant to the current conversation (compat with list or results container)."""
        try:
            tiers = None if self.use_full_memory else ["stm"]
            raw = await self.memory_manager.search_memories(
                query=query,
                limit=limit,
                min_relevance=0.3,
                tiers=tiers
            )
            # Normalize into a list of MemorySearchResult objects
            items = raw.results if hasattr(raw, "results") else raw
            results: List[MemorySearchResult] = []
            for it in (items or []):
                if isinstance(it, MemorySearchResult):
                    results.append(it)
                    continue
                if isinstance(it, dict):
                    try:
                        mem = MemoryItem.model_validate(it)
                    except Exception:
                        # Fallback if model parsing fails
                        content = it.get("content", {}) if isinstance(it.get("content"), dict) else {"text": str(it.get("content", ""))}
                        metadata = it.get("metadata", {}) if isinstance(it.get("metadata"), dict) else {}
                        mem = MemoryItem(content=content, metadata=metadata)
                    relevance = it.get("_relevance", 0.0)
                    tier = it.get("tier")
                    results.append(MemorySearchResult(memory=mem, relevance=relevance, tier=tier))
            print(f"Retrieved {len(results)} relevant memories")
            return results
        except Exception as e:
            print(f"Error during memory retrieval: {e}")
            return []

    async def process_message(self, user_message: str) -> str:
        """Process a user message and generate a response."""
        if not (user_message or "").strip():
            # Ignore empty inputs gracefully
            fallback = "I didn't catch any text. How can I help?"
            await self.store_memory(fallback, "assistant")
            self.conversation_history.append({"role": "assistant", "content": fallback})
            return fallback
        # Store the user's message in memory
        await self.store_memory(user_message, "user")
        
        # Add to conversation history
        self.conversation_history.append({"role": "user", "content": user_message})
        
        # Build memory context from working memory across tiers (full memory) if enabled
        memory_context = ""
        try:
            await self.memory_manager.update_context({"message": user_message})
            prompt_items = await self.memory_manager.get_prompt_context_memories(max_memories=8, max_tokens_per_memory=150)
            if prompt_items:
                memory_context = "Relevant previous information:\n"
                for i, item in enumerate(prompt_items, 1):
                    text = item.get("content") or ""
                    tier = item.get("tier") or "unknown"
                    rel = item.get("relevance", 0.0)
                    try:
                        memory_context += f"{i}. [tier={tier}] (Relevance: {rel:.2f}) {text}\n"
                    except Exception:
                        memory_context += f"{i}. [tier={tier}] {text}\n"
        except Exception as ctx_err:
            print(f"DEBUG: Failed to build prompt context from working memory: {ctx_err}")
            # Fallback to direct retrieval (respects scope)
            relevant_memories = await self.retrieve_relevant_memories(user_message)
            if relevant_memories:
                memory_context = "Relevant previous information:\n"
                relevant_memories.sort(key=lambda r: r.relevance, reverse=True)
                for i, search_result in enumerate(relevant_memories, 1):
                    memory_content = search_result.memory.get_text()
                    memory_context += f"{i}. (Relevance: {search_result.relevance:.2f}) {memory_content}\n"

        # Generate response using OpenAI if available
        response = ""
        if self.use_llm and self.provider == "openai" and OPENAI_AVAILABLE and getattr(self, "_openai_client", None):
            try:
                system_message = f"""You are a helpful assistant with memory capabilities.
You can remember previous parts of the conversation.

{memory_context if memory_context else "No relevant memories found."}

Base your response on the conversation history and relevant memories."""
                hist = self.conversation_history
                if self.history_window is not None:
                    hist = hist[-self.history_window:] if self.history_window > 0 else []
                messages = [
                    {"role": "system", "content": system_message},
                    *hist,
                ]
                client = self._openai_client

                def _to_plaintext(messages: list[dict[str, str]]) -> str:
                    conv_text: list[str] = []
                    for m in messages:
                        role = m.get("role", "user")
                        content = m.get("content", "")
                        conv_text.append(f"{role.upper()}: {content}")
                    return "\n\n".join(conv_text)

                completion = None

                def _responses_minimal():
                    # Responses API with minimal parameters; avoids 400s on strict models
                    return client.responses.create(
                        model=self.openai_model,
                        input=_to_plaintext(messages),
                        max_output_tokens=500,
                    )

                if self.prefer_responses:
                    # Go straight to Responses API for known strict models
                    completion = _responses_minimal()
                else:
                    # Try classic Chat Completions with full params → then progressively drop incompatible params
                    try:
                        completion = client.chat.completions.create(
                            model=self.openai_model,
                            messages=messages,
                            max_tokens=500,
                            temperature=0.7,
                            top_p=0.9,
                        )
                    except Exception as e1:
                        e1s = str(e1)
                        try:
                            if ("max_tokens" in e1s and "max_completion_tokens" in e1s):
                                completion = client.chat.completions.create(
                                    model=self.openai_model,
                                    messages=messages,
                                    max_completion_tokens=500,
                                    temperature=0.7,
                                    top_p=0.9,
                                )
                            elif "temperature" in e1s or "top_p" in e1s:
                                completion = client.chat.completions.create(
                                    model=self.openai_model,
                                    messages=messages,
                                    max_tokens=500,
                                )
                            else:
                                raise
                        except Exception:
                            completion = _responses_minimal()
                # Parse content
                content_text = ""
                try:
                    if getattr(completion, "choices", None):
                        msg = completion.choices[0].message
                        if msg:
                            print(f"DEBUG: Message object: {msg}")
                            content_text = (getattr(msg, "content", "") or "").strip()
                            if not content_text:
                                refusal = getattr(msg, "refusal", None)
                                if refusal:
                                    print(f"DEBUG: refusal: {refusal}")
                    elif hasattr(completion, "output") or hasattr(completion, "output_text"):
                        # Responses API – SDK surfaces .output or .output_text depending on version
                        content_text = getattr(completion, "output_text", None) or getattr(completion, "output", "")
                        if isinstance(content_text, str):
                            content_text = content_text.strip()
                except Exception as parse_err:
                    print(f"DEBUG: Error parsing completion: {parse_err}")

                # Retry once with a minimal nudge if empty, keeping the SAME model
                if not content_text:
                    print("DEBUG: Empty content from model; retrying with same model and explicit nudge")
                    retry_messages = list(messages) + [
                        {"role": "user", "content": "Please respond in plain text to the previous message."}
                    ]
                    try:
                        # Retry with either max_tokens or max_completion_tokens as needed
                        try:
                            if self.prefer_responses:
                                retry = client.responses.create(
                                    model=self.openai_model,
                                    input=_to_plaintext(retry_messages),
                                    max_output_tokens=400,
                                )
                            else:
                                retry = client.chat.completions.create(
                                    model=self.openai_model,
                                    messages=retry_messages,
                                    max_tokens=400,
                                    temperature=0.7,
                                    top_p=0.9,
                                )
                        except Exception as param_err2:
                            e2 = str(param_err2)
                            if not self.prefer_responses and ("max_tokens" in e2 and "max_completion_tokens" in e2):
                                retry = client.chat.completions.create(
                                    model=self.openai_model,
                                    messages=retry_messages,
                                    max_completion_tokens=400,
                                    temperature=0.7,
                                    top_p=0.9,
                                )
                            elif not self.prefer_responses and ("temperature" in e2 or "top_p" in e2):
                                retry = client.chat.completions.create(
                                    model=self.openai_model,
                                    messages=retry_messages,
                                    max_tokens=400,
                                )
                            else:
                                retry = client.responses.create(
                                    model=self.openai_model,
                                    input=_to_plaintext(retry_messages),
                                    max_output_tokens=400,
                                )
                        if getattr(retry, "choices", None):
                            rmsg = retry.choices[0].message
                            if rmsg:
                                content_text = (getattr(rmsg, "content", "") or "").strip()
                                if not content_text:
                                    rref = getattr(rmsg, "refusal", None)
                                    if rref:
                                        print(f"DEBUG: retry refusal: {rref}")
                    except Exception as retry_err:
                        print(f"DEBUG: Retry failed: {retry_err}")

                # If still empty, keep the chat flowing but DO NOT switch models
                if not content_text:
                    content_text = "Acknowledged." + (f"\n\n{memory_context}" if memory_context else "")

                response = content_text
                print("Generated response using OpenAI API (strict same-model)")
            except Exception as e:
                print(f"Error using OpenAI API: {e}")
                response = f"I'd respond to '{user_message}' here, but there was an issue with the OpenAI API. Using memory system with {self.backend_type} backend."
        elif self.use_llm and self.provider == "ollama" and 'OLLAMA_AVAILABLE' in globals() and OLLAMA_AVAILABLE:
            try:
                system_message = f"""You are a helpful assistant with memory capabilities.
You can remember previous parts of the conversation.

{memory_context if memory_context else "No relevant memories found."}

Base your response on the conversation history and relevant memories."""
                hist = self.conversation_history
                if self.history_window is not None:
                    hist = hist[-self.history_window:] if self.history_window > 0 else []
                messages = [
                    {"role": "system", "content": system_message},
                    *hist,
                ]
                result = ollama.chat(model=self.ollama_model, messages=messages)
                msg = result.get("message", {})
                response = msg.get("content") or "[Model returned empty content]"
                print(f"Generated response using Ollama ({self.ollama_model})")
            except Exception as e:
                print(f"Error using Ollama: {e}")
                response = f"I'd respond to '{user_message}' here, but there was an issue with Ollama. Using memory system with {self.backend_type} backend."
        else:
            # Fallback response without LLM
            response = f"I'd respond to '{user_message}' here. I've stored your message in my {self.backend_type} memory system."
            if memory_context:
                response += f"\n\nI remember: {memory_context}"
        
        # Store the assistant's response in memory
        await self.store_memory(response, "assistant")
        
        # Add to conversation history
        self.conversation_history.append({"role": "assistant", "content": response})
        
        return response

    async def handle_command(self, cmd: str) -> bool:
        """Handle interactive commands to stress-test memory during chat."""
        parts = (cmd or "").strip().split()
        if not parts:
            return True
        head = parts[0].lower()

        if head in ("/help", "/?"):
            print("Commands:")
            print("  /search <query>        Search memories")
            print("  /stats                 Show system stats")
            print("  /maint                 Run maintenance cycle now (consolidation/decay)")
            print("  /llm on|off            Toggle LLM usage")
            print("  /provider openai|ollama|none  Select provider")
            print("  /spam <N> [text]       Push N messages into memory (LLM disabled for speed)")
            print("  /help                  This help")
            return True

        if head == "/search" and len(parts) > 1:
            query = " ".join(parts[1:])
            results = await self.retrieve_relevant_memories(query, limit=10)
            if not results:
                print("No results")
                return True
            print("Top results:")
            for i, r in enumerate(results[:10]):
                print(f"{i+1}. ({r.relevance:.2f}) {r.memory.get_text()}")
            return True

        if head == "/stats":
            try:
                stats = await self.memory_manager.get_system_stats()
                print(json.dumps(stats, indent=2, default=str))
            except Exception as e:
                print(f"Error fetching stats: {e}")
            return True

        if head == "/maint":
            try:
                result = await self.memory_manager.run_maintenance()
                print(json.dumps(result, indent=2, default=str))
            except Exception as e:
                print(f"Error running maintenance: {e}")
            return True

        if head == "/llm" and len(parts) > 1:
            self.use_llm = parts[1].lower() == "on"
            print(f"LLM usage: {'on' if self.use_llm else 'off'}")
            return True

        if head == "/provider" and len(parts) > 1:
            choice = parts[1].lower()
            if choice in ("openai", "ollama", "none"):
                self.provider = choice
                print(f"Provider set to: {self.provider}")
            else:
                print("Unknown provider. Use: openai | ollama | none")
            return True

        if head == "/model" and len(parts) > 1:
            name = " ".join(parts[1:])
            if self.provider == "openai":
                self.openai_model = name
                print(f"OpenAI model set to: {self.openai_model}")
            elif self.provider == "ollama":
                self.ollama_model = name
                print(f"Ollama model set to: {self.ollama_model}")
            else:
                print("No provider selected. Use /provider openai|ollama first.")
            return True

        if head == "/scope" and len(parts) > 1:
            name = parts[1].lower()
            if name in ("all", "stm"):
                self.scope = name
                self.use_full_memory = (name == "all")
                print(f"Memory scope set to: {self.scope}")
            else:
                print("Unknown scope. Use: all | stm")
            return True

        if head == "/spam" and len(parts) >= 2:
            try:
                n = int(parts[1])
                payload = " ".join(parts[2:]) if len(parts) > 2 else "spam message"
                prev = self.use_llm
                self.use_llm = False
                for i in range(max(0, n)):
                    await self.store_memory(f"{payload} #{i+1}", "user", importance=0.5)
                    if (i+1) % 100 == 0:
                        print(f"Stored {i+1} messages...")
                self.use_llm = prev
                print(f"Spam complete: {n} messages stored.")
            except ValueError:
                print("Usage: /spam <N> [text]")
            return True

        return False

async def main():
    """Main function to demonstrate the agent."""
    # Parse CLI arguments
    parser = argparse.ArgumentParser(description="Conversational Memory Agent")
    parser.add_argument("--quick", action="store_true", help="Run a non-interactive quick self-test and exit")
    parser.add_argument("--provider", choices=["openai", "ollama", "none"], help="Override LLM provider")
    parser.add_argument("--llm", choices=["on", "off"], help="Toggle LLM usage")
    parser.add_argument("--backend", choices=["sqlite", "memory"], help="Select memory backend")
    parser.add_argument("--fast-tiers", action="store_true", help="Use fast tier settings to exercise STM→MTM→LTM in demo")
    parser.add_argument("--prompt", help="Prompt to use in quick mode")
    parser.add_argument(
        "--history-window",
        type=int,
        help="Only include last N conversation turns in messages (curated context is always included)",
    )
    parser.add_argument("--model", help="Model name for selected provider (e.g., gpt-5 or gemma3:4b)")
    parser.add_argument("--scope", choices=["all", "stm"], help="Memory scope: all tiers or STM only")
    args = parser.parse_args()

    # Backend selection (default: in-memory for easier testing)
    use_sqlite = (args.backend == "sqlite") if args.backend else False
    agent = ConversationalAgent(use_sqlite=use_sqlite, fast_tiers=args.fast_tiers, history_window=args.history_window)

    # Apply runtime overrides
    if args.provider:
        agent.provider = args.provider
    if args.llm:
        agent.use_llm = (args.llm == "on")
    if args.model:
        if agent.provider == "openai":
            agent.openai_model = args.model
        elif agent.provider == "ollama":
            agent.ollama_model = args.model
    if getattr(args, "scope", None):
        agent.scope = args.scope
        agent.use_full_memory = (args.scope == "all")

    quick_mode = args.quick or os.getenv("QUICK", "").strip().lower() in ("1", "true", "yes")

    try:
        # Initialize the agent
        await agent.initialize()
        
        print("\n=== Conversational Memory Agent ===")
        print("Type 'exit' to end the conversation.")
        print("Backend: " + ("SQLite" if use_sqlite else "In-Memory"))
        print("OpenAI API: " + ("Available" if OPENAI_AVAILABLE and getattr(agent, "_openai_client", None) else "Not Available"))
        print(f"Provider: {agent.provider} | Model: {(agent.openai_model if agent.provider == 'openai' else (agent.ollama_model if agent.provider == 'ollama' else 'n/a'))} | Scope: {'all' if agent.use_full_memory else 'stm'} | LLM usage: {'on' if agent.use_llm else 'off'}")
        print("Commands: /help for stress-test controls")
        print("====================================\n")

        if quick_mode:
            prompt = args.prompt or "Hello! Quick self-test."
            print(f"Quick mode: processing single prompt -> {prompt}")
            response = await agent.process_message(prompt)
            print(f"Agent: {response}")
            hits = await agent.retrieve_relevant_memories(prompt, limit=3)
            print(f"Quick self-test: {len(hits)} memory hits")
            return
        
        # Main conversation loop
        while True:
            user_input = input("\nYou: ")
            if user_input.lower() in ['exit', 'quit', 'bye']:
                break
            if user_input.startswith('/'):
                handled = await agent.handle_command(user_input)
                if handled:
                    continue
            response = await agent.process_message(user_input)
            print(f"\nAgent: {response}")
            
            # Note: The memory manager runs maintenance tasks in the background automatically
            # We just simulate a message about it for demonstration purposes
            if agent.conversation_history and len(agent.conversation_history) % 10 == 0:
                print("\nMemory system is running maintenance tasks in the background.")
                print("These tasks include consolidation (STM → MTM → LTM) and memory decay.")
    
    finally:
        # Always shutdown properly
        await agent.shutdown()

if __name__ == "__main__":
    # Run the agent
    asyncio.run(main())
