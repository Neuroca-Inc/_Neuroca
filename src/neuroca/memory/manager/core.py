"""Legacy memory manager compatibility shim.

The original `neuroca.memory.manager.core` module implemented a standalone
memory manager that diverged from the async interface-driven implementation.
Maintaining that duplicate code path introduced drift and conflicting APIs.

This module now simply re-exports the modern async `MemoryManager` so existing
imports continue to function while the project converges on the unified
implementation. Consumers should import :mod:`neuroca.memory.manager` directly
instead of this compatibility layer.
"""

from __future__ import annotations

from neuroca.memory.manager.memory_manager import MemoryManager

__all__ = ["MemoryManager"]
