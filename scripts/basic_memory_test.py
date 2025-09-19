#!/usr/bin/env python3
"""
Basic test script for the Neuroca memory system.

This script demonstrates the minimum viable use of the memory system.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Ensure repository sources are importable when running from a checkout.
ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from neuroca.memory.backends import BackendType
from neuroca.memory.manager import MemoryManager

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    """Test basic memory system functionality."""
    print("Initializing memory system...")
    
    # Create a memory manager with in-memory backend
    memory_manager = MemoryManager(
        config={
            "maintenance_interval": 0,  # disable background scheduler for cleaner demo output
            "stm": {"default_ttl": 3600},  # 1 hour TTL
            "mtm": {"max_capacity": 1000},
            "ltm": {"maintenance_interval": 86400},  # 24 hours
            "monitoring": {
                "metrics": {"enabled": False},  # silence Prometheus exporter for demo
                "events": {"enabled": False}    # silence event bus warnings for demo
            }
        },
        mtm_storage_type=BackendType.MEMORY,
        ltm_storage_type=BackendType.MEMORY,
        vector_storage_type=BackendType.MEMORY
    )
    
    try:
        # Initialize the memory manager
        await memory_manager.initialize()
        print("Memory system initialized successfully!")
        
        # Add a memory
        print("\nAdding a memory...")
        memory_id = await memory_manager.add_memory(
            content="This is a test memory",
            summary="Test memory",
            importance=0.7,
            tags=["test", "example"],
            metadata={"source": "test script", "tier": "stm"},
            initial_tier="stm",
        )
        print(f"Added memory with ID: {memory_id}")
        
        # Retrieve the memory
        print("\nRetrieving the memory...")
        memory = await memory_manager.retrieve_memory(memory_id)
        print(f"Retrieved memory: {memory}")
        
        # Search for memories
        print("\nSearching for memories...")
        results = await memory_manager.search_memories(
            query="memory",
            tiers=["stm"],
            limit=5,
        )
        # Support both current List[Dict] API and legacy-like containers with .results
        items = getattr(results, "results", results) or []
        try:
            count = len(items)
        except TypeError:
            items = list(items)
            count = len(items)

        print(f"Found {count} memories")
        for item in items:
            # Normalize across dict or object-based results
            if isinstance(item, dict):
                mid = item.get("id") or item.get("metadata", {}).get("id")
                text = (
                    (item.get("content", {}) or {}).get("text")
                    or (item.get("content", {}) or {}).get("summary")
                    or ""
                )
                relevance = item.get("_relevance", 0.0)
                tier = item.get("tier", "unknown")
            else:
                # Object-like result, e.g., _StubMemorySearchResult(memory=..., relevance=..., tier=...)
                mem = getattr(item, "memory", item)
                mid = getattr(mem, "id", None)
                # Prefer method if available
                if hasattr(mem, "get_text") and callable(getattr(mem, "get_text")):
                    text = mem.get_text()
                else:
                    text = getattr(mem, "text", "") or str(getattr(mem, "content", "") or "")
                relevance = getattr(item, "relevance", 0.0)
                tier = getattr(item, "tier", "unknown")

            print(f"- ID: {mid}, Text: {text}, Relevance: {relevance:.2f}, Tier: {tier}")

        # Wait a bit to allow background processes to run
        print("\nWaiting for 2 seconds to allow background processes to run...")
        await asyncio.sleep(2)
        
    finally:
        # Properly shut down
        print("\nShutting down memory system...")
        await memory_manager.shutdown()
        print("Memory system shut down successfully!")

if __name__ == "__main__":
    asyncio.run(main())
