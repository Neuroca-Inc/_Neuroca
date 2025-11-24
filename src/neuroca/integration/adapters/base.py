"""
Base Adapter Module for LLM Integration.

This module defines the base adapter interface and abstract classes for integrating
with various Large Language Models (LLMs). It provides a standardized way to interact
with different LLM providers while abstracting away the implementation details.

The adapter pattern used here allows the NeuroCognitive Architecture to work with
different LLMs without being tightly coupled to their specific APIs or implementations.

Classes:
    AdapterConfig: Configuration dataclass for LLM adapters
    LLMResponse: Structured response from LLM interactions
    BaseAdapter: Abstract base class for all LLM adapters
    AdapterRegistry: Registry for managing and accessing available adapters

Usage:
    Concrete adapter implementations should inherit from BaseAdapter and implement
    all abstract methods. The AdapterRegistry can be used to register and retrieve
    adapter implementations.

Example:
    ```python
    # Registering a custom adapter
    @AdapterRegistry.register("my_llm")
    class MyLLMAdapter(BaseAdapter):
        # Implementation of abstract methods
        ...

    # Using the registry to get an adapter
    adapter = AdapterRegistry.get_adapter("my_llm", config=my_config)
    response = await adapter.generate("Tell me about cognitive architectures")
    ```
"""

import abc
import asyncio
import dataclasses
import logging
import typing
from typing import Any, ClassVar, Optional, Union
from ..models import LLMRequest, LLMResponse

logger = logging.getLogger(__name__)


class AdapterError(Exception):
    """Base exception class for all adapter-related errors."""
    pass


class ConfigurationError(AdapterError):
    """Exception raised for errors in the adapter configuration."""
    pass


# Backward compatibility alias
AdapterConfigurationError = ConfigurationError


class AuthenticationError(AdapterError):
    """Exception raised for authentication failures with the LLM provider."""
    pass


class RateLimitError(AdapterError):
    """Exception raised when LLM provider rate limits are exceeded."""
    pass


class ServiceUnavailableError(AdapterError):
    """Exception raised when the LLM service is unavailable."""
    pass


class InvalidRequestError(AdapterError):
    """Exception raised for invalid requests to the LLM provider."""
    pass


class TokenLimitExceededError(AdapterError):
    """Exception raised when the token limit is exceeded."""
    pass


class ResponseFormatError(AdapterError):
    """Exception raised when the LLM response cannot be properly parsed."""
    pass


class ModelNotFoundError(AdapterError):
    """Exception raised when the requested model is not found."""
    pass


class AdapterNotFoundError(AdapterError):
    """Exception raised when a requested adapter is not found in the registry."""
    pass


# ResponseType is imported from ..models (canonical)


@dataclasses.dataclass
class AdapterConfig:
    """
    Configuration for LLM adapters.
    
    This dataclass holds all necessary configuration parameters for initializing
    and operating an LLM adapter. It provides a standardized way to configure
    different adapters with their specific requirements.
    
    Attributes:
        model_name (str): Name of the LLM model to use
        api_key (Optional[str]): API key for authentication with the LLM provider
        api_base (Optional[str]): Base URL for the LLM API
        timeout (float): Timeout in seconds for API calls
        max_retries (int): Maximum number of retries for failed API calls
        retry_delay (float): Delay between retries in seconds
        temperature (float): Sampling temperature for generation (0.0 to 1.0)
        max_tokens (Optional[int]): Maximum tokens to generate in responses
        top_p (float): Nucleus sampling parameter (0.0 to 1.0)
        top_k (Optional[int]): Top-k sampling parameter
        presence_penalty (float): Presence penalty for token generation
        frequency_penalty (float): Frequency penalty for token generation
        stop_sequences (Optional[List[str]]): Sequences that stop generation
        extra_params (Dict[str, Any]): Additional model-specific parameters
    """
    model_name: str
    api_key: Optional[str] = None
    api_base: Optional[str] = None
    timeout: float = 60.0
    max_retries: int = 3
    retry_delay: float = 1.0
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    top_p: float = 1.0
    top_k: Optional[int] = None
    presence_penalty: float = 0.0
    frequency_penalty: float = 0.0
    stop_sequences: Optional[list[str]] = None
    extra_params: dict[str, Any] = dataclasses.field(default_factory=dict)

    def __post_init__(self):
        """Validate configuration after initialization."""
        if not self.model_name:
            raise ConfigurationError("model_name must be specified")
        
        if self.temperature < 0.0 or self.temperature > 1.0:
            raise ConfigurationError("temperature must be between 0.0 and 1.0")
        
        if self.top_p < 0.0 or self.top_p > 1.0:
            raise ConfigurationError("top_p must be between 0.0 and 1.0")
        
        if self.timeout <= 0:
            raise ConfigurationError("timeout must be positive")
        
        if self.max_retries < 0:
            raise ConfigurationError("max_retries cannot be negative")
        
        if self.retry_delay < 0:
            raise ConfigurationError("retry_delay cannot be negative")

    def to_dict(self) -> dict[str, Any]:
        """Convert configuration to dictionary, excluding sensitive information."""
        config_dict = dataclasses.asdict(self)
        # Remove sensitive information
        if 'api_key' in config_dict:
            config_dict['api_key'] = '***' if config_dict['api_key'] else None
        return config_dict


# LLMResponse is imported from ..models (canonical)


class BaseAdapter(abc.ABC):
    """
    Abstract base class for all LLM adapters.
    
    This class defines the interface that all concrete LLM adapters must implement.
    It provides common functionality and enforces a consistent API across different
    LLM integrations.
    
    Attributes:
        config (AdapterConfig): Configuration for the adapter
        name (ClassVar[str]): Name identifier for the adapter
    """
    name: ClassVar[str] = "base"
    
    def __init__(self, config: AdapterConfig):
        """
        Initialize the adapter with the provided configuration.
        
        Args:
            config: Configuration for the adapter
            
        Raises:
            ConfigurationError: If the configuration is invalid
        """
        self.config = config
        self.validate_config()
        self._setup_logging()
        logger.info(f"Initialized {self.__class__.__name__} adapter with model: {config.model_name}")

    def _setup_logging(self):
        """Configure adapter-specific logging."""
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def validate_config(self):
        """
        Validate that the configuration is suitable for this adapter.
        
        Raises:
            ConfigurationError: If the configuration is invalid for this adapter
        """
        # Base validation is handled by AdapterConfig.__post_init__
        # Subclasses should override to add adapter-specific validation
        pass

    @abc.abstractmethod
    async def generate(self, prompt: str, **kwargs) -> LLMResponse:
        """
        Generate a text response from the LLM based on the provided prompt.
        
        Args:
            prompt: The text prompt to send to the LLM
            **kwargs: Additional parameters to override configuration
            
        Returns:
            LLMResponse containing the generated text
            
        Raises:
            AdapterError: If an error occurs during generation
        """
        pass

    @abc.abstractmethod
    async def generate_chat(self, messages: list[dict[str, str]], **kwargs) -> LLMResponse:
        """
        Generate a response from the LLM based on a conversation history.
        
        Args:
            messages: List of message dictionaries with 'role' and 'content' keys
            **kwargs: Additional parameters to override configuration
            
        Returns:
            LLMResponse containing the generated response
            
        Raises:
            AdapterError: If an error occurs during generation
        """
        pass

    @abc.abstractmethod
    async def generate_embedding(self, text: Union[str, list[str]], **kwargs) -> LLMResponse:
        """
        Generate embeddings for the provided text(s).
        
        Args:
            text: Single text or list of texts to embed
            **kwargs: Additional parameters to override configuration
            
        Returns:
            LLMResponse containing the embeddings
            
        Raises:
            AdapterError: If an error occurs during embedding generation
        """
        pass

    @abc.abstractmethod
    async def generate_with_functions(
        self, 
        messages: list[dict[str, str]], 
        functions: list[dict[str, Any]], 
        **kwargs
    ) -> LLMResponse:
        """
        Generate a response that may include function calls.
        
        Args:
            messages: List of message dictionaries with 'role' and 'content' keys
            functions: List of function definitions the LLM can call
            **kwargs: Additional parameters to override configuration
            
        Returns:
            LLMResponse containing the generated response or function call
            
        Raises:
            AdapterError: If an error occurs during generation
        """
        pass

    async def _execute_with_retry(
        self, 
        operation: typing.Callable[[], typing.Awaitable[Any]], 
        max_retries: Optional[int] = None, 
        retry_delay: Optional[float] = None
    ) -> Any:
        """
        Execute an async operation with retry logic.
        
        Args:
            operation: Async callable to execute
            max_retries: Maximum number of retries (defaults to config value)
            retry_delay: Delay between retries in seconds (defaults to config value)
            
        Returns:
            Result of the operation
            
        Raises:
            AdapterError: If all retries fail
        """
        max_retries = max_retries if max_retries is not None else self.config.max_retries
        retry_delay = retry_delay if retry_delay is not None else self.config.retry_delay
        
        retries = 0
        last_error = None
        
        while retries <= max_retries:
            try:
                return await operation()
            except RateLimitError as e:
                last_error = e
                wait_time = retry_delay * (2 ** retries)  # Exponential backoff
                self.logger.warning(
                    f"Rate limit exceeded. Retrying in {wait_time:.2f}s ({retries}/{max_retries})"
                )
            except (ServiceUnavailableError, ConnectionError) as e:
                last_error = e
                wait_time = retry_delay * (2 ** retries)  # Exponential backoff
                self.logger.warning(
                    f"Service unavailable. Retrying in {wait_time:.2f}s ({retries}/{max_retries})"
                )
            except Exception as e:
                # Don't retry other types of errors
                self.logger.error(f"Operation failed: {str(e)}")
                raise
            
            retries += 1
            if retries <= max_retries:
                await asyncio.sleep(wait_time)
        
        self.logger.error(f"Operation failed after {max_retries} retries: {str(last_error)}")
        raise last_error

    def get_merged_params(self, **kwargs) -> dict[str, Any]:
        """
        Merge configuration with provided parameters.
        
        Args:
            **kwargs: Parameters to override configuration
            
        Returns:
            Dictionary of merged parameters
        """
        # Start with the configuration parameters
        params = {
            "model": self.config.model_name,
            "temperature": self.config.temperature,
            "top_p": self.config.top_p,
        }
        
        # Add optional parameters if they exist in config
        if self.config.max_tokens is not None:
            params["max_tokens"] = self.config.max_tokens
        if self.config.top_k is not None:
            params["top_k"] = self.config.top_k
        if self.config.stop_sequences is not None:
            params["stop"] = self.config.stop_sequences
        if self.config.presence_penalty != 0.0:
            params["presence_penalty"] = self.config.presence_penalty
        if self.config.frequency_penalty != 0.0:
            params["frequency_penalty"] = self.config.frequency_penalty
            
        # Add any extra parameters from config
        params.update(self.config.extra_params)
        
        # Override with any provided kwargs
        params.update(kwargs)
        
        return params

    async def execute(self, request: LLMRequest) -> LLMResponse:
        """
        Default standardized execution path for adapters.
        Routes LLMRequest to generate() and coerces to canonical LLMResponse.
        Subclasses may override for provider-specific execution.
        """
        if request.prompt is None:
            raise InvalidRequestError("LLMRequest.prompt must be provided for text generation")
        # Build parameter map from request
        params: dict[str, Any] = {}
        if request.model is not None:
            params["model"] = request.model
        if request.max_tokens is not None:
            params["max_tokens"] = request.max_tokens
        if request.temperature is not None:
            params["temperature"] = request.temperature
        if request.stop_sequences is not None:
            params["stop_sequences"] = request.stop_sequences
        if request.additional_params:
            params.update(request.additional_params)

        resp = await self.generate(request.prompt, **params)

        if isinstance(resp, LLMResponse):
            if resp.request is None:
                resp.request = request
            return resp

        # Legacy fallback: coerce simple content to canonical response
        content = None
        raw = None
        if isinstance(resp, dict):
            content = resp.get("content") or resp.get("response") or resp.get("text") or ""
            raw = resp
        else:
            content = str(resp)

        return LLMResponse(
            provider=getattr(self, "name", "unknown"),
            model=request.model or self.config.model_name,
            content=content,
            raw_response=raw,
            request=request,
        )

    async def close(self) -> None:
        """Optional hook for adapters to release resources."""
        return None

    def get_available_models(self) -> list[str]:
        """
        Default implementation returns an empty list.
        Adapters may override to return a cached list of models.
        """
        try:
            if getattr(self, "config", None) and getattr(self.config, "model_name", None):
                return [self.config.model_name]
        except Exception:
            pass
        return []

    def __str__(self) -> str:
        """String representation of the adapter."""
        return f"{self.__class__.__name__}(model={self.config.model_name})"

    def __repr__(self) -> str:
        """Detailed string representation of the adapter."""
        return f"{self.__class__.__name__}(config={self.config})"


class AdapterRegistry:
    """
    Registry for managing and accessing available LLM adapters.
    
    This class provides a centralized registry for adapter implementations,
    allowing them to be registered, discovered, and instantiated by name.
    """
    _adapters: dict[str, type[BaseAdapter]] = {}
    
    @classmethod
    def register(cls, name: Optional[str] = None):
        """
        Decorator to register an adapter class in the registry.
        
        Args:
            name: Optional name for the adapter (defaults to adapter's name attribute)
            
        Returns:
            Decorator function
            
        Example:
            ```python
            @AdapterRegistry.register("openai")
            class OpenAIAdapter(BaseAdapter):
                name = "openai"
                # Implementation...
            ```
        """
        def decorator(adapter_cls: type[BaseAdapter]) -> type[BaseAdapter]:
            adapter_name = name or adapter_cls.name
            if not adapter_name:
                raise ValueError("Adapter must have a name attribute or provide a name parameter")
            
            if adapter_name in cls._adapters:
                logger.warning(f"Overwriting existing adapter registration for '{adapter_name}'")
                
            cls._adapters[adapter_name] = adapter_cls
            logger.debug(f"Registered adapter '{adapter_name}'")
            return adapter_cls
        
        return decorator
    
    @classmethod
    def get_adapter_class(cls, name: str) -> type[BaseAdapter]:
        """
        Get an adapter class by name.
        
        Args:
            name: Name of the adapter to retrieve
            
        Returns:
            The adapter class
            
        Raises:
            AdapterNotFoundError: If no adapter with the given name is registered
        """
        if name not in cls._adapters:
            raise AdapterNotFoundError(f"No adapter registered with name '{name}'")
        return cls._adapters[name]
    
    @classmethod
    def get_adapter(cls, name: str, config: AdapterConfig) -> BaseAdapter:
        """
        Get an instantiated adapter by name.
        
        Args:
            name: Name of the adapter to retrieve
            config: Configuration for the adapter
            
        Returns:
            An instantiated adapter
            
        Raises:
            AdapterNotFoundError: If no adapter with the given name is registered
        """
        adapter_cls = cls.get_adapter_class(name)
        return adapter_cls(config)
    
    @classmethod
    def list_adapters(cls) -> list[str]:
        """
        List all registered adapter names.
        
        Returns:
            List of registered adapter names
        """
        return list(cls._adapters.keys())
    
    @classmethod
    def unregister(cls, name: str) -> None:
        """
        Unregister an adapter by name.
        
        Args:
            name: Name of the adapter to unregister
            
        Raises:
            AdapterNotFoundError: If no adapter with the given name is registered
        """
        if name not in cls._adapters:
            raise AdapterNotFoundError(f"No adapter registered with name '{name}'")
        del cls._adapters[name]
        logger.debug(f"Unregistered adapter '{name}'")
