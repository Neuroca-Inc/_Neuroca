"""
Core Models Package for NeuroCognitive Architecture (NCA)

This package contains the core domain models that represent the fundamental
entities and concepts within the NeuroCognitive Architecture system. These models
form the foundation of the system's domain logic and are used throughout the application.

The models in this package follow domain-driven design principles and are designed
to be persistence-agnostic, focusing on business logic and domain rules rather than
storage concerns.

Usage:
    from neuroca.core.models import BaseModel, ModelRegistry
    from neuroca.core.models.cognitive import CognitiveState
    from neuroca.core.models.memory import MemoryItem

Models are organized into submodules by domain area:
- base: Base model classes and common utilities
- cognitive: Models related to cognitive processes and states
- memory: Models for the three-tiered memory system
- health: Models for system health and monitoring
- agent: Models for agent behavior and characteristics

This module exports commonly used models directly for convenience while
maintaining the ability to import specific models from their respective submodules.
"""

import logging
from typing import Dict, List, Optional, Set, Type, TypeVar, Union

# Configure module-level logger
logger = logging.getLogger(__name__)

# Import and re-export base models and utilities
from neuroca.core.models.base import (  # noqa: E402
    BaseModel,
    ModelRegistry,
    Serializable,
    ValidationError,
    ModelID,
    ModelNotFoundError,
)

# Import and re-export cognitive models
from neuroca.core.models.cognitive import (  # noqa: E402
    Attention,
    CognitiveProcess,
    CognitiveState,
    WorkingMemoryBuffer,
)

# Import and re-export memory models
from neuroca.core.models.memory import (  # noqa: E402
    MemoryContent,
    MemoryItem,
    MemoryMetadata,
    MemorySearchOptions,
    MemorySearchResult,
    MemoryStatus,
    WorkingMemoryItem,
)

# Import and re-export health models
from neuroca.core.models.health import (  # noqa: E402
    HealthMetrics,
    PerformanceIndicators,
    ResourceUtilization,
    SystemState,
)

# Import and re-export agent models
from neuroca.core.models.agent import (  # noqa: E402
    Agent,
    AgentCapability,
    AgentProfile,
    AgentState,
)

# User models
from neuroca.core.models.user import (  # noqa: E402
    CognitiveProfile,
    User,
    UserPreferences,
    UserRole,
)

# Metrics models
from neuroca.core.models.metrics import (  # noqa: E402
    MemoryMetrics,
    MetricDefinition,
    MetricSummary,
    MetricTimeseriesData,
    MetricType,
    PerformanceMetrics,
    SystemHealthMetrics,
)

# Type variable for generic model operations
T = TypeVar('T', bound=BaseModel)

# Define what's available for import from this package
__all__ = [
    # Base models
    'BaseModel',
    'ModelRegistry',
    'Serializable',
    'ValidationError',
    'ModelID',
    'ModelNotFoundError',

    # Cognitive models
    'CognitiveState',
    'CognitiveProcess',
    'Attention',
    'WorkingMemoryBuffer',

    # Memory models
    'MemoryContent',
    'MemoryItem',
    'MemoryMetadata',
    'MemoryStatus',
    'MemorySearchResult',
    'MemorySearchOptions',
    'WorkingMemoryItem',

    # Health models
    'HealthMetrics',
    'SystemState',
    'ResourceUtilization',
    'PerformanceIndicators',

    # Agent models
    'Agent',
    'AgentProfile',
    'AgentCapability',
    'AgentState',

    # User models
    'User',
    'UserPreferences',
    'UserRole',
    'CognitiveProfile',

    # Metrics
    'MetricType',
    'MetricDefinition',
    'MetricSummary',
    'MetricTimeseriesData',
    'MemoryMetrics',
    'PerformanceMetrics',
    'SystemHealthMetrics',
]

# Initialize the model registry
model_registry = ModelRegistry()

# Register all models with the registry
def register_models() -> None:
    """
    Register all model classes with the global model registry.
    This enables model lookup, validation, and other registry-based operations.
    
    This function should be called during application initialization.
    
    Returns:
        None
    
    Raises:
        ImportError: If critical model modules cannot be imported
        RuntimeError: If model registration fails
    """
    try:
        for model_class in [cls for name, cls in globals().items() 
                           if isinstance(cls, type) and issubclass(cls, BaseModel) and cls != BaseModel]:
            model_registry.register(model_class)
        logger.info(f"Successfully registered {len(model_registry)} models")
    except Exception as e:
        logger.error(f"Error registering models: {str(e)}")
        raise RuntimeError(f"Failed to register models: {str(e)}") from e

# Version information
__version__ = '0.1.0'

logger.debug(f"Initialized core models package v{__version__}")