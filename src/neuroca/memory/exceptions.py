"""
Memory Exceptions (Stub)

This module provides stub implementations of memory exceptions to satisfy imports
while the main memory system uses the tier-based architecture.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class MemoryCapacityError(Exception):
    """Exception raised when memory capacity is exceeded."""

    pass


class MemoryBackpressureError(Exception):
    """Exception raised when ingestion is throttled due to back-pressure."""

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

    def __init__(
        self,
        message: Optional[str] = None,
        *,
        backend_type: Optional[str] = None,
        operation: Optional[str] = None,
    ) -> None:
        self.backend_type = backend_type
        self.operation = operation
        if message is None:
            context: list[str] = []
            if backend_type:
                context.append(f"backend={backend_type}")
            if operation:
                context.append(f"operation={operation}")
            detail = f" ({', '.join(context)})" if context else ""
            message = f"Storage operation failed{detail}".strip()
        super().__init__(message)


class StorageBackendError(Exception):
    """Exception raised when storage backend operations fail."""

    def __init__(
        self,
        message: Optional[str] = None,
        *,
        backend_type: Optional[str] = None,
    ) -> None:
        self.backend_type = backend_type
        if message is None:
            detail = f" for backend {backend_type}" if backend_type else ""
            message = f"Storage backend error{detail}".strip()
        super().__init__(message)


class StorageInitializationError(Exception):
    """Exception raised when storage initialization fails."""

    def __init__(
        self,
        message: Optional[str] = None,
        *,
        backend_type: Optional[str] = None,
    ) -> None:
        self.backend_type = backend_type
        if message is None:
            detail = f" for backend {backend_type}" if backend_type else ""
            message = f"Failed to initialize storage backend{detail}".strip()
        super().__init__(message)


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

    def __init__(
        self,
        message: Optional[str] = None,
        *,
        tier_name: Optional[str] = None,
    ) -> None:
        self.tier_name = tier_name
        if message is None:
            detail = f" for tier {tier_name}" if tier_name else ""
            message = f"Failed to initialize memory tier{detail}".strip()
        super().__init__(message)
