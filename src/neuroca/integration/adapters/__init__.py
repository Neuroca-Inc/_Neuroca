"""
Adapters Module for NeuroCognitive Architecture (NCA)

This module provides the adapter interface and registry for integrating with various
Large Language Models (LLMs). The adapter pattern allows the NCA system to interact
with different LLM providers through a consistent interface, abstracting away the
implementation details of each specific LLM API.

Usage:
    from neuroca.integration.adapters import AdapterRegistry, BaseAdapter

    # Get a registered adapter class
    openai_adapter_cls = AdapterRegistry.get_adapter_class("openai")
    # Instantiate (assuming config is loaded)
    # openai_adapter = openai_adapter_cls(config=provider_config)

    # Or create and register instance directly if registry manages instances
    # openai_adapter = AdapterRegistry.create_adapter("openai", **provider_config)

    # Use the adapter
    # response = await openai_adapter.generate(prompt="Tell me about cognitive architecture")

    # Register a custom adapter class
    # AdapterRegistry.register_adapter_class("my_custom_llm", MyCustomAdapter)
"""

import logging
from enum import Enum

# Configure module logger
logger = logging.getLogger(__name__)

# --- Import concrete adapter implementations ---
# Attempt to import adapters, handle potential ImportError if dependencies aren't installed
try:
    from .openai import OpenAIAdapter
except ImportError:
    OpenAIAdapter = None
    logger.debug("OpenAI adapter not available (openai package likely not installed)")

try:
    from .anthropic import AnthropicAdapter
except ImportError:
    AnthropicAdapter = None
    logger.debug("Anthropic adapter not available (anthropic package likely not installed)")

try:
    from .vertexai import VertexAIAdapter
except ImportError:
    VertexAIAdapter = None
    logger.debug("VertexAI adapter not available (google-cloud-aiplatform package likely not installed)")

try:
    from .ollama import OllamaAdapter
except ImportError:
    OllamaAdapter = None
    logger.debug("Ollama adapter not available (aiohttp package likely not installed)")

# --- Import Base Class, Registry, and Core Exceptions/Enums from base.py ---
# This centralizes the core definitions.
try:
    from .base import (
        AdapterConfigurationError,
        AdapterError,
        AdapterNotFoundError,
        AdapterRegistry,
        BaseAdapter,
    )
    from ..models import LLMResponse, ResponseType
except ImportError as exc:
    logger.error(
        "Failed to import adapter components. Adapters may not function correctly.",
        exc_info=exc,
    )

    class BaseAdapter:  # pragma: no cover - import fallback
        """Fallback adapter base class used when core adapter components are unavailable."""

        def __init__(self, *args: object, **kwargs: object) -> None:
            """Initialise the placeholder adapter without performing any work."""

    class AdapterRegistry:  # pragma: no cover - import fallback
        """Fallback registry that keeps module imports functional in degraded mode."""

        @classmethod
        def register(cls, name: str | None = None):
            """Return a decorator that leaves the provided adapter class unchanged."""

            def decorator(adapter_cls):
                """Return the provided adapter class unchanged."""

                return adapter_cls

            return decorator

        @classmethod
        def get_adapter_class(cls, name: str):
            """Return ``None`` while the real registry is unavailable."""

            return None

        @classmethod
        def list_adapters(cls):
            """Return an empty list because no adapters can be discovered."""

            return []

    class AdapterError(Exception):  # pragma: no cover - import fallback
        """Base placeholder error raised by the degraded adapter registry."""

    class AdapterNotFoundError(AdapterError):  # pragma: no cover - import fallback
        """Placeholder raised when an adapter cannot be located in degraded mode."""

    class AdapterConfigurationError(AdapterError):  # pragma: no cover - import fallback
        """Placeholder raised when adapter configuration fails in degraded mode."""

    class LLMResponse:  # pragma: no cover - import fallback
        """Lightweight response placeholder returned while adapters are unavailable."""

        def __init__(self, *args: object, **kwargs: object) -> None:
            """Initialise the placeholder response with no behaviour."""

    class ResponseType(Enum):  # pragma: no cover - import fallback
        """Placeholder enumeration for response typing when adapters are unavailable."""

        GENERIC = "generic"

# --- Automatically register available built-in adapters ---
# Ensure AdapterRegistry was imported successfully before trying to use it
if 'AdapterRegistry' in globals():
    if OpenAIAdapter:
        AdapterRegistry.register("openai")(OpenAIAdapter)
    if AnthropicAdapter:
        AdapterRegistry.register("anthropic")(AnthropicAdapter)
    if VertexAIAdapter:
        AdapterRegistry.register("vertexai")(VertexAIAdapter)
    if OllamaAdapter:
        AdapterRegistry.register("ollama")(OllamaAdapter)
else:
    logger.error("AdapterRegistry not available for automatic registration.")


# --- Define public exports for the package ---
__all__ = [
    "BaseAdapter",
    "AdapterRegistry",
    "AdapterError",
    "AdapterNotFoundError",
    "AdapterConfigurationError",
    "LLMResponse",
    "ResponseType",
    # Export available adapter classes if they were imported successfully
]

# Dynamically add imported adapters to __all__
if OpenAIAdapter:
    __all__.append("OpenAIAdapter")
if AnthropicAdapter:
    __all__.append("AnthropicAdapter")
if VertexAIAdapter:
    __all__.append("VertexAIAdapter")
if OllamaAdapter:
    __all__.append("OllamaAdapter")
