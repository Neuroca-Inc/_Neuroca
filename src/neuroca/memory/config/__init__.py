"""
Memory Configuration Package

This package provides configuration management utilities for the memory system.
It includes configuration loading, validation, and access utilities.
"""

from neuroca.memory.config.embedding import (
    DEFAULT_EMBEDDING_DIMENSION,
    ensure_embedding_dimension_fields,
    resolve_embedding_dimension,
)
from neuroca.memory.config.validation import validate_memory_manager_configuration
from neuroca.memory.config.loader import (
    ConfigurationLoader,
    get_backend_config,
    get_config_value,
    config_loader,
)

__all__ = [
    'ConfigurationLoader',
    'get_backend_config',
    'get_config_value',
    'config_loader',
    'DEFAULT_EMBEDDING_DIMENSION',
    'resolve_embedding_dimension',
    'ensure_embedding_dimension_fields',
    'validate_memory_manager_configuration',
]
