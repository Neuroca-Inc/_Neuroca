"""
Core Exceptions for NeuroCognitive Architecture (NCA).

This module defines custom exception classes used throughout the NCA system.
These exceptions provide specific error types for different components and
operations, enabling better error handling and debugging.

The exceptions are organized into categories:
- Memory System Exceptions
- API Exceptions  
- Authentication Exceptions
- Storage Exceptions
- Health System Exceptions

Each exception includes descriptive messages and context to aid in troubleshooting.
"""

import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class NeuroCAError(Exception):
    """Base exception class for all NeuroCognitive Architecture errors."""
    
    def __init__(self, message: str, error_code: Optional[str] = None, context: Optional[Dict[str, Any]] = None):
        """
        Initialize a NeuroCognitive Architecture error.
        
        Args:
            message: Human-readable error message
            error_code: Optional error code for programmatic handling
            context: Optional context information for debugging
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.context = context or {}
        
        # Log the error for debugging
        logger.error(f"NeuroCAError: {message}", extra={
            "error_code": error_code,
            "context": context
        })


# Memory System Exceptions

class MemoryError(NeuroCAError):
    """Base exception for memory system errors."""
    pass


class MemoryNotFoundError(MemoryError):
    """Raised when a requested memory item cannot be found."""
    
    def __init__(self, memory_id: str, message: Optional[str] = None):
        """
        Initialize a memory not found error.
        
        Args:
            memory_id: The ID of the memory that was not found
            message: Optional custom message
        """
        self.memory_id = memory_id
        default_message = f"Memory with ID '{memory_id}' not found"
        super().__init__(
            message or default_message,
            error_code="MEMORY_NOT_FOUND",
            context={"memory_id": memory_id}
        )


class MemoryStorageError(MemoryError):
    """Raised when there's an error storing or retrieving memory data."""
    
    def __init__(self, operation: str, message: Optional[str] = None, cause: Optional[Exception] = None):
        """
        Initialize a memory storage error.
        
        Args:
            operation: The storage operation that failed
            message: Optional custom message
            cause: Optional underlying exception that caused this error
        """
        self.operation = operation
        self.cause = cause
        default_message = f"Memory storage operation '{operation}' failed"
        if cause:
            default_message += f": {str(cause)}"
        
        super().__init__(
            message or default_message,
            error_code="MEMORY_STORAGE_ERROR",
            context={"operation": operation, "cause": str(cause) if cause else None}
        )


class MemoryTierFullError(MemoryError):
    """Raised when attempting to store memory in a full tier."""
    
    def __init__(self, tier: str, capacity: Optional[int] = None, current_count: Optional[int] = None):
        """
        Initialize a memory tier full error.
        
        Args:
            tier: The memory tier that is full
            capacity: Optional maximum capacity of the tier
            current_count: Optional current number of items in the tier
        """
        self.tier = tier
        self.capacity = capacity
        self.current_count = current_count
        
        message = f"Memory tier '{tier}' is full"
        if capacity and current_count:
            message += f" ({current_count}/{capacity})"
        
        super().__init__(
            message,
            error_code="MEMORY_TIER_FULL",
            context={
                "tier": tier,
                "capacity": capacity,
                "current_count": current_count
            }
        )


class MemoryAccessDeniedError(MemoryError):
    """Raised when access to a memory item is denied."""
    
    def __init__(self, memory_id: str, user_id: str, operation: str, message: Optional[str] = None):
        """
        Initialize a memory access denied error.
        
        Args:
            memory_id: The ID of the memory being accessed
            user_id: The ID of the user attempting access
            operation: The operation being attempted
            message: Optional custom message
        """
        self.memory_id = memory_id
        self.user_id = user_id
        self.operation = operation
        
        default_message = f"Access denied for user '{user_id}' to memory '{memory_id}' for operation '{operation}'"
        
        super().__init__(
            message or default_message,
            error_code="MEMORY_ACCESS_DENIED",
            context={
                "memory_id": memory_id,
                "user_id": user_id,
                "operation": operation
            }
        )


class MemoryValidationError(MemoryError):
    """Raised when memory data fails validation."""

    def __init__(self, field: str, value: Any, message: Optional[str] = None):
        """
        Initialize a memory validation error.

        Args:
            field: The field that failed validation
            value: The invalid value
            message: Optional custom message
        """
        self.field = field
        self.value = value

        default_message = f"Validation failed for field '{field}' with value '{value}'"

        super().__init__(
            message or default_message,
            error_code="MEMORY_VALIDATION_ERROR",
            context={"field": field, "value": str(value)}
        )


# Prompt Exceptions


class PromptError(NeuroCAError):
    """Base exception for prompt generation and validation errors."""


class InvalidPromptParameterError(PromptError):
    """Raised when a prompt parameter fails validation."""

    def __init__(self, parameter: str, message: Optional[str] = None, value: Any = None):
        """Initialise an invalid prompt parameter error."""

        context = {"parameter": parameter}
        if value is not None:
            context["value"] = value

        default_message = message or f"Invalid value for prompt parameter '{parameter}'"
        super().__init__(
            default_message,
            error_code="PROMPT_PARAMETER_INVALID",
            context=context,
        )


class PromptGenerationError(PromptError):
    """Raised when a prompt cannot be generated."""

    def __init__(self, message: str, cause: Optional[Exception] = None):
        context = {"cause": str(cause) if cause else None}
        if cause:
            logger.error("Prompt generation failed", exc_info=cause)
        super().__init__(
            message,
            error_code="PROMPT_GENERATION_ERROR",
            context=context,
        )


class PromptValidationError(PromptError):
    """Raised when prompt content fails validation checks."""

    def __init__(self, message: str, field: Optional[str] = None):
        context = {"field": field} if field else None
        super().__init__(
            message,
            error_code="PROMPT_VALIDATION_ERROR",
            context=context,
        )


class ReasoningError(PromptError):
    """Raised when reasoning workflows fail."""

    def __init__(self, message: str, cause: Optional[Exception] = None):
        context = {"cause": str(cause) if cause else None}
        super().__init__(
            message,
            error_code="PROMPT_REASONING_ERROR",
            context=context,
        )


# API Exceptions

class APIError(NeuroCAError):
    """Base exception for API-related errors."""
    pass


class InvalidRequestError(APIError):
    """Raised when an API request is malformed or invalid."""
    
    def __init__(self, details: str, message: Optional[str] = None):
        """
        Initialize an invalid request error.
        
        Args:
            details: Details about what made the request invalid
            message: Optional custom message
        """
        self.details = details
        default_message = f"Invalid request: {details}"
        
        super().__init__(
            message or default_message,
            error_code="INVALID_REQUEST",
            context={"details": details}
        )


class RateLimitExceededError(APIError):
    """Raised when API rate limits are exceeded."""
    
    def __init__(self, limit: int, window: str, message: Optional[str] = None):
        """
        Initialize a rate limit exceeded error.
        
        Args:
            limit: The rate limit that was exceeded
            window: The time window for the rate limit
            message: Optional custom message
        """
        self.limit = limit
        self.window = window
        
        default_message = f"Rate limit exceeded: {limit} requests per {window}"
        
        super().__init__(
            message or default_message,
            error_code="RATE_LIMIT_EXCEEDED",
            context={"limit": limit, "window": window}
        )


# Authentication Exceptions

class AuthenticationError(NeuroCAError):
    """Base exception for authentication errors."""
    pass


class InvalidTokenError(AuthenticationError):
    """Raised when an authentication token is invalid."""
    
    def __init__(self, reason: str, message: Optional[str] = None):
        """
        Initialize an invalid token error.
        
        Args:
            reason: The reason the token is invalid
            message: Optional custom message
        """
        self.reason = reason
        default_message = f"Invalid token: {reason}"
        
        super().__init__(
            message or default_message,
            error_code="INVALID_TOKEN",
            context={"reason": reason}
        )


class ExpiredTokenError(AuthenticationError):
    """Raised when an authentication token has expired."""
    
    def __init__(self, token_type: str, expired_at: str, message: Optional[str] = None):
        """
        Initialize an expired token error.
        
        Args:
            token_type: The type of token that expired
            expired_at: When the token expired
            message: Optional custom message
        """
        self.token_type = token_type
        self.expired_at = expired_at
        
        default_message = f"{token_type} token expired at {expired_at}"
        
        super().__init__(
            message or default_message,
            error_code="EXPIRED_TOKEN",
            context={"token_type": token_type, "expired_at": expired_at}
        )


class InsufficientPermissionsError(AuthenticationError):
    """Raised when a user lacks required permissions."""
    
    def __init__(self, user_id: str, required_permissions: list[str], message: Optional[str] = None):
        """
        Initialize an insufficient permissions error.
        
        Args:
            user_id: The ID of the user lacking permissions
            required_permissions: The permissions that were required
            message: Optional custom message
        """
        self.user_id = user_id
        self.required_permissions = required_permissions
        
        default_message = f"User '{user_id}' lacks required permissions: {', '.join(required_permissions)}"
        
        super().__init__(
            message or default_message,
            error_code="INSUFFICIENT_PERMISSIONS",
            context={"user_id": user_id, "required_permissions": required_permissions}
        )


# Storage Exceptions

class StorageError(NeuroCAError):
    """Base exception for storage backend errors."""
    pass


class StorageConnectionError(StorageError):
    """Raised when unable to connect to a storage backend."""
    
    def __init__(self, backend_type: str, connection_string: str, message: Optional[str] = None):
        """
        Initialize a storage connection error.
        
        Args:
            backend_type: The type of storage backend
            connection_string: The connection string (sanitized)
            message: Optional custom message
        """
        self.backend_type = backend_type
        self.connection_string = connection_string
        
        default_message = f"Failed to connect to {backend_type} storage: {connection_string}"
        
        super().__init__(
            message or default_message,
            error_code="STORAGE_CONNECTION_ERROR",
            context={"backend_type": backend_type, "connection_string": connection_string}
        )


class StorageConfigurationError(StorageError):
    """Raised when storage backend configuration is invalid."""
    
    def __init__(self, backend_type: str, config_issue: str, message: Optional[str] = None):
        """
        Initialize a storage configuration error.
        
        Args:
            backend_type: The type of storage backend
            config_issue: Description of the configuration issue
            message: Optional custom message
        """
        self.backend_type = backend_type
        self.config_issue = config_issue
        
        default_message = f"Invalid {backend_type} storage configuration: {config_issue}"
        
        super().__init__(
            message or default_message,
            error_code="STORAGE_CONFIGURATION_ERROR",
            context={"backend_type": backend_type, "config_issue": config_issue}
        )


# Health System Exceptions

class HealthSystemError(NeuroCAError):
    """Base exception for health system errors."""
    pass


class HealthMetricError(HealthSystemError):
    """Raised when there's an error with health metrics."""
    
    def __init__(self, metric_name: str, operation: str, message: Optional[str] = None):
        """
        Initialize a health metric error.
        
        Args:
            metric_name: The name of the health metric
            operation: The operation that failed
            message: Optional custom message
        """
        self.metric_name = metric_name
        self.operation = operation
        
        default_message = f"Health metric '{metric_name}' {operation} failed"
        
        super().__init__(
            message or default_message,
            error_code="HEALTH_METRIC_ERROR",
            context={"metric_name": metric_name, "operation": operation}
        )


class HealthThresholdExceededError(HealthSystemError):
    """Raised when a health metric exceeds safe thresholds."""
    
    def __init__(self, metric_name: str, current_value: float, threshold: float, message: Optional[str] = None):
        """
        Initialize a health threshold exceeded error.
        
        Args:
            metric_name: The name of the health metric
            current_value: The current value of the metric
            threshold: The threshold that was exceeded
            message: Optional custom message
        """
        self.metric_name = metric_name
        self.current_value = current_value
        self.threshold = threshold
        
        default_message = f"Health metric '{metric_name}' exceeded threshold: {current_value} > {threshold}"
        
        super().__init__(
            message or default_message,
            error_code="HEALTH_THRESHOLD_EXCEEDED",
            context={
                "metric_name": metric_name,
                "current_value": current_value,
                "threshold": threshold
            }
        )


# LLM Integration Exceptions

class LLMError(NeuroCAError):
    """Base exception for LLM integration errors."""
    pass


class LLMProviderError(LLMError):
    """Raised when there's an error with an LLM provider."""
    
    def __init__(self, provider: str, operation: str, details: str, message: Optional[str] = None):
        """
        Initialize an LLM provider error.
        
        Args:
            provider: The name of the LLM provider
            operation: The operation that failed
            details: Details about the error
            message: Optional custom message
        """
        self.provider = provider
        self.operation = operation
        self.details = details
        
        default_message = f"LLM provider '{provider}' {operation} failed: {details}"
        
        super().__init__(
            message or default_message,
            error_code="LLM_PROVIDER_ERROR",
            context={"provider": provider, "operation": operation, "details": details}
        )


class LLMQuotaExceededError(LLMError):
    """Raised when LLM usage quota is exceeded."""
    
    def __init__(self, provider: str, quota_type: str, limit: int, message: Optional[str] = None):
        """
        Initialize an LLM quota exceeded error.
        
        Args:
            provider: The name of the LLM provider
            quota_type: The type of quota exceeded (e.g., 'tokens', 'requests')
            limit: The quota limit that was exceeded
            message: Optional custom message
        """
        self.provider = provider
        self.quota_type = quota_type
        self.limit = limit
        
        default_message = f"LLM {quota_type} quota exceeded for provider '{provider}': {limit}"
        
        super().__init__(
            message or default_message,
            error_code="LLM_QUOTA_EXCEEDED",
            context={"provider": provider, "quota_type": quota_type, "limit": limit}
        )


# Database Exceptions

class DatabaseError(NeuroCAError):
    """Base exception for database errors."""
    pass


class ConnectionError(DatabaseError):
    """Raised when database connection fails."""
    pass


class QueryError(DatabaseError):
    """Raised when database query fails."""
    pass


# Configuration Exceptions

class ConfigurationError(NeuroCAError):
    """Base exception for configuration errors."""
    pass


class MissingConfigurationError(ConfigurationError):
    """Raised when required configuration is missing."""
    
    def __init__(self, config_key: str, component: str, message: Optional[str] = None):
        """
        Initialize a missing configuration error.
        
        Args:
            config_key: The configuration key that is missing
            component: The component that requires the configuration
            message: Optional custom message
        """
        self.config_key = config_key
        self.component = component
        
        default_message = f"Missing required configuration '{config_key}' for component '{component}'"
        
        super().__init__(
            message or default_message,
            error_code="MISSING_CONFIGURATION",
            context={"config_key": config_key, "component": component}
        )


class InvalidConfigurationError(ConfigurationError):
    """Raised when configuration values are invalid."""
    
    def __init__(self, config_key: str, value: Any, reason: str, message: Optional[str] = None):
        """
        Initialize an invalid configuration error.
        
        Args:
            config_key: The configuration key with invalid value
            value: The invalid value
            reason: The reason the value is invalid
            message: Optional custom message
        """
        self.config_key = config_key
        self.value = value
        self.reason = reason
        
        default_message = f"Invalid configuration value for '{config_key}': {value} ({reason})"
        
        super().__init__(
            message or default_message,
            error_code="INVALID_CONFIGURATION",
            context={"config_key": config_key, "value": str(value), "reason": reason}
        )


# Utility Functions

def format_exception_context(exception: NeuroCAError) -> str:
    """
    Format exception context for logging or display.
    
    Args:
        exception: The NeuroCognitive Architecture exception
        
    Returns:
        Formatted string representation of the exception context
    """
    if not exception.context:
        return exception.message
    
    context_parts = [f"{key}={value}" for key, value in exception.context.items()]
    return f"{exception.message} [{', '.join(context_parts)}]"


def is_retriable_error(exception: Exception) -> bool:
    """
    Determine if an error is retriable.
    
    Args:
        exception: The exception to check
        
    Returns:
        True if the error is retriable, False otherwise
    """
    # Network-related errors are typically retriable
    retriable_errors = [
        StorageConnectionError,
        LLMProviderError,
    ]
    
    # Quota and permission errors are typically not retriable
    non_retriable_errors = [
        MemoryAccessDeniedError,
        InsufficientPermissionsError,
        LLMQuotaExceededError,
        ExpiredTokenError,
        InvalidTokenError,
    ]
    
    if any(isinstance(exception, error_type) for error_type in non_retriable_errors):
        return False
    
    if any(isinstance(exception, error_type) for error_type in retriable_errors):
        return True
    
    # Default to not retriable for unknown errors
    return False
