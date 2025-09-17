"""Tests for legacy memory manager compatibility shims."""

import importlib

from neuroca.memory.manager import AsyncMemoryManager, MemoryManager
from neuroca.memory.manager.memory_manager import MemoryManager as Implementation


def test_public_memory_manager_exports_single_implementation() -> None:
    """Package-level exports should point at the async implementation."""

    assert MemoryManager is Implementation
    assert AsyncMemoryManager is Implementation


def test_legacy_core_module_reexports_async_manager() -> None:
    """Legacy module path should resolve to the unified implementation."""

    legacy_module = importlib.import_module("neuroca.memory.manager.core")
    assert legacy_module.MemoryManager is Implementation
