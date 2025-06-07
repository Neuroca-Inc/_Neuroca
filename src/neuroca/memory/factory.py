"""
Memory System Factory for NeuroCognitive Architecture.

This module provides factory functions for creating and configuring memory systems
with different backends and configurations. It serves as the main entry point for
initializing memory systems in the NCA architecture.

Usage:
    from neuroca.memory.factory import create_memory_system
    
    # Create a memory system with default configuration
    memory_system = create_memory_system()
    
    # Create with specific backend
    memory_system = create_memory_system(backend_type="sqlite")
    
    # Create with custom configuration
    config = {"database_path": "/path/to/memory.db"}
    memory_system = create_memory_system(backend_type="sqlite", config=config)
"""

import logging
from typing import Any, Dict, Optional

from neuroca.memory.manager import MemoryManager
from neuroca.memory.backends.factory import StorageBackendFactory
from neuroca.memory.backends.base import BackendType
from neuroca.config.settings import get_settings

logger = logging.getLogger(__name__)


def create_memory_system(
    backend_type: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None,
    **kwargs
) -> MemoryManager:
    """
    Factory function to create a fully configured memory system.
    
    This function creates and initializes a memory system with the specified
    backend and configuration. It handles the creation of storage backends,
    memory managers, and all associated components.
    
    Args:
        backend_type: Type of storage backend to use (in_memory, sqlite, redis, etc.)
        config: Configuration dictionary for the memory system
        **kwargs: Additional keyword arguments passed to the memory manager
    
    Returns:
        MemoryManager: Configured and initialized memory manager instance
    
    Raises:
        ValueError: If an invalid backend type is specified
        RuntimeError: If memory system initialization fails
    """
    logger.info("Creating memory system with backend: %s", backend_type or "default")
    
    try:
        # Load default configuration from settings
        settings = get_settings()
        default_config = {
            "backend_type": backend_type or settings.get("MEMORY_BACKEND_TYPE", "in_memory"),
            "max_memory_size": int(settings.get("MEMORY_MAX_SIZE", 1000)),
            "consolidation_interval": int(settings.get("MEMORY_CONSOLIDATION_INTERVAL", 3600)),
            "decay_rate": float(settings.get("MEMORY_DECAY_RATE", 0.1)),
        }
        
        # Merge with provided configuration
        if config:
            default_config.update(config)
        
        # Create storage backend
        backend_type_enum = BackendType(default_config["backend_type"])
        storage_backend = StorageBackendFactory.create_backend(
            backend_type_enum,
            default_config
        )
        
        # Create memory manager
        memory_manager = MemoryManager(
            storage_backend=storage_backend,
            config=default_config,
            **kwargs
        )
        
        logger.info("Successfully created memory system with %s backend", backend_type_enum.value)
        return memory_manager
        
    except Exception as e:
        logger.error("Failed to create memory system: %s", str(e))
        raise RuntimeError(f"Memory system creation failed: {str(e)}") from e


def create_test_memory_system(
    backend_type: str = "in_memory",
    config: Optional[Dict[str, Any]] = None
) -> MemoryManager:
    """
    Factory function to create a memory system for testing purposes.
    
    This function creates a memory system optimized for testing with
    sensible defaults and minimal external dependencies.
    
    Args:
        backend_type: Type of storage backend to use (defaults to in_memory)
        config: Configuration dictionary for the memory system
    
    Returns:
        MemoryManager: Configured memory manager instance for testing
    """
    logger.debug("Creating test memory system with backend: %s", backend_type)
    
    test_config = {
        "backend_type": backend_type,
        "max_memory_size": 100,  # Smaller for testing
        "consolidation_interval": 60,  # More frequent for testing
        "decay_rate": 0.05,  # Slower decay for testing
        "enable_persistence": False,  # Disable persistence for tests
    }
    
    if config:
        test_config.update(config)
    
    return create_memory_system(backend_type=backend_type, config=test_config)


def get_available_backends() -> list[str]:
    """
    Get a list of available memory backends.
    
    Returns:
        List[str]: List of available backend type names
    """
    return [backend_type.value for backend_type in BackendType]


def validate_backend_config(
    backend_type: str,
    config: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Validate and normalize configuration for a specific backend type.
    
    Args:
        backend_type: The backend type to validate configuration for
        config: Configuration dictionary to validate
    
    Returns:
        Dict[str, Any]: Validated and normalized configuration
    
    Raises:
        ValueError: If the configuration is invalid for the backend type
    """
    logger.debug("Validating configuration for backend: %s", backend_type)
    
    try:
        backend_type_enum = BackendType(backend_type)
    except ValueError as e:
        available_backends = get_available_backends()
        raise ValueError(
            f"Invalid backend type '{backend_type}'. "
            f"Available backends: {', '.join(available_backends)}"
        ) from e
    
    # Backend-specific validation
    validated_config = config.copy()
    
    if backend_type_enum == BackendType.SQLITE:
        # Ensure database path is provided
        if "database_path" not in validated_config:
            validated_config["database_path"] = ":memory:"  # Default to in-memory SQLite
    
    elif backend_type_enum == BackendType.REDIS:
        # Ensure Redis connection parameters
        validated_config.setdefault("host", "localhost")
        validated_config.setdefault("port", 6379)
        validated_config.setdefault("db", 0)
    
    elif backend_type_enum == BackendType.SQL:
        # Ensure database URL is provided
        if "database_url" not in validated_config:
            raise ValueError("SQL backend requires 'database_url' in configuration")
    
    elif backend_type_enum == BackendType.VECTOR:
        # Ensure vector database configuration
        validated_config.setdefault("dimension", 512)
        validated_config.setdefault("metric", "cosine")
    
    logger.debug("Configuration validated successfully for %s backend", backend_type)
    return validated_config


# Convenience aliases for backward compatibility
create_memory_manager = create_memory_system
create_test_memory_manager = create_test_memory_system

# Export factory functions
__all__ = [
    "create_memory_system",
    "create_test_memory_system",
    "create_memory_manager",  # Alias
    "create_test_memory_manager",  # Alias
    "get_available_backends",
    "validate_backend_config",
]
