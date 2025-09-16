"""
Storage Backend Factory

This module provides the StorageBackendFactory class for creating storage backend instances.
The factory is responsible for creating the appropriate backend based on
configuration settings and ensures only one instance of each backend is created.
"""

import inspect
import logging
from typing import Any, Dict, Optional, Type

# Set up logger first so we can use it in the try-except blocks below
logger = logging.getLogger(__name__)

from neuroca.memory.backends.base import BaseStorageBackend
from neuroca.memory.backends.factory.backend_type import BackendType
from neuroca.memory.backends.factory.memory_tier import MemoryTier
from neuroca.memory.backends.in_memory_backend import InMemoryBackend
from neuroca.memory.backends.sqlite_backend import SQLiteBackend
# Import Redis conditionally as it requires external dependencies
try:
    from neuroca.memory.backends.redis_backend import RedisBackend
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.warning("Redis backend not available. Install redis for Redis support.")
from neuroca.memory.backends.sql_backend import SQLBackend
# Vector backend is optional depending on feature completeness
try:
    from neuroca.memory.backends.vector_backend import VectorBackend

    _VECTOR_METHODS = ("store", "retrieve", "update", "delete", "search")
    VECTOR_AVAILABLE = all(hasattr(VectorBackend, method) for method in _VECTOR_METHODS)
    if not VECTOR_AVAILABLE:
        logger.warning(
            "Vector backend missing required methods %s; skipping registration until implementation is complete",
            [method for method in _VECTOR_METHODS if not hasattr(VectorBackend, method)],
        )
except ImportError:
    VECTOR_AVAILABLE = False
    logger.warning("Vector backend not available. Install vector extras for support.")

from neuroca.memory.exceptions import ConfigurationError


_SENSITIVE_KEYS = {"password", "secret", "token", "key", "api_key", "access_token"}


def _redact_sensitive(values: Dict[str, Any]) -> Dict[str, Any]:
    """Return a copy of *values* with potentially secret fields redacted."""

    redacted: Dict[str, Any] = {}
    for key, value in values.items():
        redacted[key] = "***REDACTED***" if key.lower() in _SENSITIVE_KEYS else value
    return redacted


class StorageBackendFactory:
    """
    Factory for creating storage backend instances.
    
    This class is responsible for creating and configuring storage backend
    instances based on the provided configuration. It ensures that the
    appropriate backend is created for each memory tier.
    """
    
    # Registry of backend implementations
    _backend_registry: Dict[BackendType, Type[BaseStorageBackend]] = {
        BackendType.MEMORY: InMemoryBackend,
        BackendType.SQL: SQLBackend,
        BackendType.SQLITE: SQLiteBackend,
    }

    # Add Redis backend only if it's available
    if REDIS_AVAILABLE:
        _backend_registry[BackendType.REDIS] = RedisBackend
    if VECTOR_AVAILABLE:
        _backend_registry[BackendType.VECTOR] = VectorBackend
    
    # Instances of created backends (for reuse)
    _instances: Dict[str, BaseStorageBackend] = {}
    
    @classmethod
    def create_storage(
        cls,
        tier: Optional[MemoryTier] = None,
        backend_type: Optional[BackendType] = None,
        config: Optional[Dict[str, Any]] = None,
        use_existing: bool = True,
        instance_name: Optional[str] = None,
    ) -> BaseStorageBackend:
        """
        Create and initialize a storage backend instance.
        
        Args:
            tier: Memory tier for which to create the backend (determines default backend type)
            backend_type: Explicit backend type to create (overrides tier default)
            config: Backend-specific configuration
            use_existing: Whether to reuse an existing instance if available
            instance_name: Optional name for the instance (for reuse identification)
            
        Returns:
            Initialized storage backend instance
            
        Raises:
            ConfigurationError: If the specified backend type is not supported
        """
        config = config or {}
        
        # Determine the backend type
        if backend_type is None:
            if tier is None:
                # Default to in-memory backend if neither tier nor type is specified
                backend_type = BackendType.MEMORY
            else:
                # Determine default backend type based on tier
                backend_type = cls._get_default_backend_for_tier(tier)
        
        # Get the backend class
        if backend_type not in cls._backend_registry:
            raise ConfigurationError(
                component="StorageBackendFactory",
                message=f"Unsupported backend type: {backend_type}. "
                f"Supported types: {list(cls._backend_registry.keys())}"
            )
        
        backend_class = cls._backend_registry[backend_type]
        
        # Generate instance name (for registry)
        if instance_name is None:
            if tier is not None:
                instance_name = f"{tier.value}_{backend_type.value}"
            else:
                instance_name = f"{backend_type.value}"
                
            # Add identifier based on selected config values if present
            if "database" in config:
                instance_name += f"_{config['database']}"
            elif "host" in config and "port" in config:
                instance_name += f"_{config['host']}_{config['port']}"
        
        # Check if instance already exists
        if use_existing and instance_name in cls._instances:
            logger.debug(f"Reusing existing backend instance: {instance_name}")
            return cls._instances[instance_name]
        
        # Prepare keyword arguments for backend initialization
        logger.info(f"Creating new {backend_type.value} storage backend for {tier.value if tier else 'custom'} tier")

        init_signature = inspect.signature(backend_class)
        parameters = init_signature.parameters
        accepts_var_kwargs = any(param.kind == inspect.Parameter.VAR_KEYWORD for param in parameters.values())
        positional_only_params = [
            name
            for name, param in parameters.items()
            if param.kind == inspect.Parameter.POSITIONAL_ONLY
        ]
        if positional_only_params:
            raise TypeError(
                "Backend class '%s' has positional-only parameters %s. "
                "Only keyword arguments are supported for backend initialization."
                % (backend_class.__name__, positional_only_params)
            )

        provided_config = config.copy() if isinstance(config, dict) else {}
        init_kwargs: Dict[str, Any] = {}
        residual_config: Dict[str, Any] = {}

        for key, value in provided_config.items():
            if key in parameters or accepts_var_kwargs:
                init_kwargs[key] = value
            else:
                residual_config[key] = value

        if "config" in parameters and residual_config:
            existing_config = init_kwargs.get("config")
            if isinstance(existing_config, dict):
                merged_config = existing_config.copy()
                merged_config.update(residual_config)
                init_kwargs["config"] = merged_config
            elif existing_config is None:
                init_kwargs["config"] = residual_config
        elif residual_config:
            if accepts_var_kwargs:
                init_kwargs.update(residual_config)
            else:
                init_kwargs["config"] = residual_config

        try:
            backend = backend_class(**init_kwargs)
        except TypeError as error:
            logger.error(
                "Failed to initialize backend %s with kwargs %s: %s",
                backend_class.__name__,
                _redact_sensitive(init_kwargs),
                error,
            )
            raise

        # Store the instance for reuse
        cls._instances[instance_name] = backend

        return backend
    
    @classmethod
    def register_backend(cls, backend_type: BackendType, backend_class: Type[BaseStorageBackend]) -> None:
        """
        Register a new backend implementation.
        
        Args:
            backend_type: The backend type to register
            backend_class: The backend class implementation
        """
        cls._backend_registry[backend_type] = backend_class
        logger.info(f"Registered {backend_class.__name__} implementation for {backend_type.value} backend")
    
    @classmethod
    def get_registry(cls) -> Dict[BackendType, Type[BaseStorageBackend]]:
        """
        Get the current backend registry.
        
        Returns:
            Dictionary mapping backend types to their implementations
        """
        return cls._backend_registry.copy()
    
    @classmethod
    def get_existing_instances(cls) -> Dict[str, BaseStorageBackend]:
        """
        Get all existing backend instances.
        
        Returns:
            Dictionary mapping instance names to their instances
        """
        return cls._instances.copy()
    
    @classmethod
    def shutdown_all(cls) -> None:
        """
        Shutdown all created backend instances.
        """
        for instance_name, backend in list(cls._instances.items()):
            try:
                # Shutting down is an async operation, but we're calling it
                # in a synchronous context here for simplicity. In a real
                # implementation, this would need to be properly handled.
                import asyncio
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        loop.create_task(backend.shutdown())
                    else:
                        loop.run_until_complete(backend.shutdown())
                except RuntimeError:
                    # If there's no event loop, create one
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(backend.shutdown())
                    loop.close()
                
                del cls._instances[instance_name]
                logger.info(f"Shutdown backend instance: {instance_name}")
            except Exception as e:
                logger.exception(f"Error shutting down backend instance {instance_name}: {str(e)}")
    
    @classmethod
    def _get_default_backend_for_tier(cls, tier: MemoryTier) -> BackendType:
        """
        Get the default backend type for a memory tier.
        
        Args:
            tier: The memory tier
            
        Returns:
            The default backend type for the tier
        """
        import os
        env = os.environ.get("NEUROCA_ENV", "development")
        
        if tier == MemoryTier.STM:
            # STM: Fast access for working memory
            if env in ("production", "staging"):
                return BackendType.REDIS if REDIS_AVAILABLE else BackendType.MEMORY
            else:
                return BackendType.MEMORY  # Development/testing
                
        elif tier == MemoryTier.MTM:
            # MTM: Structured storage for medium-term memory
            if env in ("production", "staging"):
                return BackendType.SQLITE  # Persistent structured storage
            else:
                return BackendType.MEMORY  # Development/testing
                
        elif tier == MemoryTier.LTM:
            # LTM: Long-term semantic storage
            if env in ("production", "staging"):
                return BackendType.SQL  # Full SQL backend for complex queries
            else:
                return BackendType.SQLITE  # SQLite for development
        else:
            return BackendType.MEMORY  # Default fallback
