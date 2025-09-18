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

from neuroca.config.settings import get_settings
from neuroca.memory.backends.factory import StorageBackendFactory
from neuroca.memory.backends.factory.backend_type import BackendType
from neuroca.memory.backends.factory.memory_tier import MemoryTier
from neuroca.memory.config import ensure_embedding_dimension_fields, resolve_embedding_dimension
from neuroca.memory.config.validation import validate_memory_manager_configuration
from neuroca.memory.manager.memory_manager import MemoryManager
from neuroca.memory.tiers.ltm.core import LongTermMemoryTier
from neuroca.memory.tiers.mtm.core import MediumTermMemoryTier
from neuroca.memory.tiers.stm.core import ShortTermMemoryTier
logger = logging.getLogger(__name__)


def _deep_merge_dicts(target: Dict[str, Any], updates: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively merge two dictionaries with list concatenation support."""

    result = dict(target)
    for key, value in updates.items():
        if key in result:
            current = result[key]
            if isinstance(current, dict) and isinstance(value, dict):
                result[key] = _deep_merge_dicts(current, value)
            elif isinstance(current, list) and isinstance(value, list):
                result[key] = current + value
            else:
                result[key] = value
        else:
            result[key] = value
    return result


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
        backend_type: Type of storage backend to use (memory, sqlite, redis, etc.)
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
        settings_config: Dict[str, Any] = {}
        try:
            settings = get_settings()
            memory_settings = getattr(settings, "MEMORY_SYSTEM", None)
            if memory_settings is not None:
                if hasattr(memory_settings, "model_dump"):
                    settings_config = memory_settings.model_dump()
                elif hasattr(memory_settings, "dict"):
                    settings_config = memory_settings.dict()
        except Exception as settings_error:  # pragma: no cover - defensive logging
            logger.debug("Unable to load memory settings: %s", settings_error)

        base_config: Dict[str, Any] = {
            "maintenance_interval": settings_config.get("CONSOLIDATION_INTERVAL", 3600),
            "stm": {},
            "mtm": {},
            "ltm": {},
        }

        merged_config = _deep_merge_dicts(base_config, config or {})

        embedding_override = kwargs.pop("embedding_dimension", None)
        embedding_dimension = resolve_embedding_dimension(
            explicit_override=embedding_override,
            manager_config=merged_config,
            settings_config=settings_config,
        )
        ensure_embedding_dimension_fields(merged_config, dimension=embedding_dimension)
        validate_memory_manager_configuration(
            merged_config,
            settings_config=settings_config if isinstance(settings_config, dict) else None,
        )

        def _normalize_backend(value: Optional[str | BackendType]) -> Optional[BackendType]:
            if value is None:
                return None
            if isinstance(value, BackendType):
                return value
            normalized = value.lower()
            backend_type_map = {
                "in_memory": BackendType.MEMORY.value,
                "memory": BackendType.MEMORY.value,
                "sqlite": BackendType.SQLITE.value,
                "redis": BackendType.REDIS.value,
                "vector": BackendType.VECTOR.value,
                "sql": BackendType.SQL.value,
            }
            normalized = backend_type_map.get(normalized, normalized)
            try:
                return BackendType(normalized)
            except ValueError:
                logger.warning(
                    "Unknown backend type '%s' requested; ignoring override and using tier defaults",
                    value,
                )
                return None

        fallback_backend = _normalize_backend(backend_type)
        backend_overrides = merged_config.get("backend_types", {}) if isinstance(merged_config.get("backend_types"), dict) else {}
        shared_storage_config = merged_config.get("storage", {}) if isinstance(merged_config.get("storage"), dict) else {}

        def _prepare_tier(
            tier_name: str,
            tier_enum: MemoryTier,
        ) -> tuple[
            ShortTermMemoryTier | MediumTermMemoryTier | LongTermMemoryTier,
            Dict[str, Any],
            Optional[BackendType],
        ]:
            tier_settings_raw = merged_config.get(tier_name, {})
            tier_settings = dict(tier_settings_raw) if isinstance(tier_settings_raw, dict) else {}

            backend_value = tier_settings.get("backend_type")
            if backend_value is None and isinstance(backend_overrides, dict):
                backend_value = backend_overrides.get(tier_name)
            if backend_value is None:
                backend_value = merged_config.get(f"{tier_name}_backend_type")

            backend_enum = _normalize_backend(backend_value) or fallback_backend

            storage_specific = tier_settings.get("storage", {})
            storage_config = dict(shared_storage_config)
            if isinstance(storage_specific, dict):
                storage_config.update(storage_specific)

            tier_config = {k: v for k, v in tier_settings.items() if k not in {"backend_type", "storage"}}

            storage_backend = StorageBackendFactory.create_storage(
                tier=tier_enum,
                backend_type=backend_enum,
                config=storage_config or None,
            )

            tier_kwargs = {
                "storage_backend": storage_backend,
                "backend_type": backend_enum,
                "backend_config": storage_config or None,
                "config": tier_config or None,
            }

            if tier_enum == MemoryTier.STM:
                tier_instance = ShortTermMemoryTier(**tier_kwargs)
            elif tier_enum == MemoryTier.MTM:
                tier_instance = MediumTermMemoryTier(**tier_kwargs)
            else:
                tier_instance = LongTermMemoryTier(**tier_kwargs)

            return tier_instance, tier_config, backend_enum

        stm_tier, stm_config, stm_backend_type = _prepare_tier("stm", MemoryTier.STM)
        mtm_tier, mtm_config, mtm_backend_type = _prepare_tier("mtm", MemoryTier.MTM)
        ltm_tier, ltm_config, ltm_backend_type = _prepare_tier("ltm", MemoryTier.LTM)

        manager_config = {
            "stm": stm_config,
            "mtm": mtm_config,
            "ltm": ltm_config,
            "maintenance_interval": merged_config.get("maintenance_interval", 3600),
        }

        memory_manager = MemoryManager(
            config=manager_config,
            backend_config=shared_storage_config,
            stm=stm_tier,
            mtm=mtm_tier,
            ltm=ltm_tier,
            stm_storage_type=stm_backend_type,
            mtm_storage_type=mtm_backend_type,
            ltm_storage_type=ltm_backend_type,
            embedding_dimension=embedding_dimension,
            **kwargs,
        )

        logger.info("Successfully created memory system with tier backends: stm=%s mtm=%s ltm=%s",
                    stm_backend_type.value if stm_backend_type else "default",
                    mtm_backend_type.value if mtm_backend_type else "default",
                    ltm_backend_type.value if ltm_backend_type else "default")
        return memory_manager
        
    except Exception as e:
        logger.error("Failed to create memory system: %s", str(e))
        raise RuntimeError(f"Memory system creation failed: {str(e)}") from e


def create_test_memory_system(
    backend_type: str = BackendType.MEMORY.value,
    config: Optional[Dict[str, Any]] = None
) -> MemoryManager:
    """
    Factory function to create a memory system for testing purposes.
    
    This function creates a memory system optimized for testing with
    sensible defaults and minimal external dependencies.
    
    Args:
        backend_type: Type of storage backend to use (defaults to in-memory backend)
        config: Configuration dictionary for the memory system
    
    Returns:
        MemoryManager: Configured memory manager instance for testing
    """
    logger.debug("Creating test memory system with backend: %s", backend_type)
    
    test_config: Dict[str, Any] = {
        "maintenance_interval": 60,
        "backend_types": {
            "stm": backend_type,
            "mtm": backend_type,
            "ltm": backend_type,
        },
        "stm": {
            "ttl_seconds": 300,
            "decay_rate": 0.05,
        },
        "mtm": {
            "max_capacity": 100,
        },
        "ltm": {
            "pruning_interval": 600,
        },
    }

    if config:
        def _deep_merge(target: Dict[str, Any], updates: Dict[str, Any]) -> Dict[str, Any]:
            result = dict(target)
            for key, value in updates.items():
                if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                    result[key] = _deep_merge(result[key], value)
                else:
                    result[key] = value
            return result

        test_config = _deep_merge_dicts(test_config, config)

    return create_memory_system(config=test_config)


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
