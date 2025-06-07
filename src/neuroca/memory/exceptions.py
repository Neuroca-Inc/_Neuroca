"""
Memory Exceptions (Stub)

This module provides stub implementations of memory exceptions to satisfy imports
while the main memory system uses the tier-based architecture.
"""

import logging

logger = logging.getLogger(__name__)


class MemoryCapacityError(Exception):
    """Exception raised when memory capacity is exceeded."""
    pass


class MemoryRetrievalError(Exception):
    """Exception raised when memory retrieval fails."""
    pass


class MemoryStorageError(Exception):
    """Exception raised when memory storage fails."""
    pass


class MemoryConsolidationError(Exception):
    """Exception raised when memory consolidation fails."""
    pass


class MemoryDecayError(Exception):
    """Exception raised when memory decay fails."""
    pass


# Storage-related exceptions
class StorageOperationError(Exception):
    """Exception raised when storage operations fail."""
    pass


class StorageBackendError(Exception):
    """Exception raised when storage backend operations fail."""
    pass


class StorageInitializationError(Exception):
    """Exception raised when storage initialization fails."""
    pass


class ItemNotFoundError(Exception):
    """Exception raised when an item is not found in storage."""
    pass


class ItemExistsError(Exception):
    """Exception raised when attempting to create an item that already exists."""
    pass


class ConfigurationError(Exception):
    """Exception raised when configuration is invalid."""
    pass


# Additional tier-related exceptions
class TierOperationError(Exception):
    """Exception raised when tier operations fail."""
    
    def __init__(self, message: str = None, operation: str = None, tier_name: str = None):
        self.operation = operation
        self.tier_name = tier_name
        if message:
            super().__init__(message)
        else:
            super().__init__(f"Tier operation failed: {operation} in {tier_name}")


class MemoryNotFoundError(Exception):
    """Exception raised when a memory item is not found."""
    pass


class InvalidTierError(Exception):
    """Exception raised when an invalid tier is specified."""
    pass


class MemoryManagerInitializationError(Exception):
    """Exception raised when memory manager initialization fails."""
    pass


class MemoryManagerOperationError(Exception):
    """Exception raised when memory manager operations fail."""
    pass


class TierInitializationError(Exception):
    """Exception raised when tier initialization fails."""
    pass
