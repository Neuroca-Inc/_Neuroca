"""Context injection orchestration for NeuroCognitive Architecture.

Purpose:
    Coordinate enrichment of LLM prompts with conversational history and memory
    context while respecting configurable token budgets.
External Dependencies:
    No direct CLI or HTTP integrations; relies on standard library components
    and internal NeuroCA data models.
Fallback Semantics:
    Failures raise explicit exceptions so callers can trigger their own fallback
    strategies; no silent degradation is performed here.
Timeout Strategy:
    Operations run synchronously in memory and do not enforce additional timeouts
    beyond the token budget heuristics.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Union

from neuroca.config.context_injection import (
    ContextInjectionConfig,
    get_default_context_injection_config,
)
from neuroca.core.exceptions import ContextWindowExceededError, InvalidContextFormatError
from neuroca.integration.context.injection_formatters import (
    estimate_structured_token_count,
    format_context,
)
from neuroca.integration.context.injection_selection import (
    prepare_context_elements,
    select_context_elements,
)
from neuroca.integration.context.injection_types import (
    ContextElement as ContextElement,
    ContextFormat as ContextFormat,
    ContextInjectionStrategy as ContextInjectionStrategy,
    ContextPriority as ContextPriority,
)
from neuroca.memory.models import MemoryRetrievalResult

__all__ = [
    "ContextPriority",
    "ContextElement",
    "ContextFormat",
    "ContextInjectionStrategy",
    "ContextInjectionManager",
    "ContextInjector",
    "inject_context",
]

logger = logging.getLogger(__name__)


class ContextInjectionManager:
    """Coordinate context assembly and injection for outbound prompts.

    Summary:
        Wraps helper routines that prepare, select, and format contextual
        elements prior to dispatching a prompt to an LLM provider.
    Attributes:
        config (ContextInjectionConfig): Resolved configuration payload.
        max_tokens (int): Maximum tokens allowed for the final prompt plus context.
        reserved_tokens (int): Tokens reserved for the LLM response window.
        format (ContextFormat): Provider-specific formatting directive.
        strategy (ContextInjectionStrategy): Strategy describing how context is merged.
        token_counter (Callable[[str], int]): Callable used to estimate token counts.
    Side Effects:
        Emits structured debug/info logs describing prioritisation, selection,
        and formatting behaviour.
    Timeout/Retry Notes:
        No explicit timeout or retry handling; callers should wrap invocation in
        application-level timeout controls when necessary.
    """

    def __init__(self, config: ContextInjectionConfig):
        """Initialise the context injection manager with validated configuration.

        Summary:
            Stores configuration-driven limits and prepares helper utilities that
            orchestrate context assembly.
        Parameters:
            config (ContextInjectionConfig): Validated configuration describing
                token budgets, formatting preferences, and selection strategy.
        Returns:
            None
        Raises:
            ValueError: Propagated if ``config`` fails its internal validation checks.
        Side Effects:
            Caches a token counting callable and emits a debug statement describing
            the active strategy and token budget.
        Timeout/Retry Notes:
            No timeout handling occurs; construction completes synchronously.
        """

        self.config = config
        self.max_tokens = config.max_context_window_tokens
        self.reserved_tokens = config.reserved_tokens_for_response
        self.format = ContextFormat(config.context_format)
        self.strategy = ContextInjectionStrategy(config.injection_strategy)
        self.token_counter = self._resolve_token_counter()
        logger.debug(
            "Initialized ContextInjectionManager with format=%s, strategy=%s, max_tokens=%s",
            self.format.value,
            self.strategy.value,
            self.max_tokens,
        )

    def _resolve_token_counter(self) -> Callable[[str], int]:
        """Return the token counting callable for the active configuration.

        Summary:
            Provides a lightweight default token counter (whitespace tokenizer)
            while allowing future extensions to inject provider-specific logic.
        Parameters:
            None
        Returns:
            Callable[[str], int]: Token counting function.
        Raises:
            None
        Side Effects:
            None.
        Timeout/Retry Notes:
            Not applicable.
        """

        return lambda text: len(text.split())

    def inject_context(
        self,
        *,
        prompt: str,
        conversation_history: list[dict[str, str]] | None = None,
        memory_retrieval_results: list[MemoryRetrievalResult] | None = None,
        system_instructions: str | None = None,
        additional_context: dict[str, Any] | None = None,
    ) -> Union[str, dict[str, Any]]:
        """Inject relevant context into the prompt based on available information.

        Summary:
            Prepares candidate context elements, applies token-aware selection,
            and formats the surviving elements according to the configured strategy.
        Parameters:
            prompt (str): The user's current prompt/query.
            conversation_history (list[dict[str, str]] | None): Previous conversation turns.
            memory_retrieval_results (list[MemoryRetrievalResult] | None): Results from memory systems.
            system_instructions (str | None): System-level instructions for the LLM.
            additional_context (dict[str, Any] | None): Additional context payloads to consider.
        Returns:
            Union[str, dict[str, Any]]: Enhanced prompt with injected context, formatted for the target LLM.
        Raises:
            ContextWindowExceededError: If the resulting context exceeds the maximum token limit.
            InvalidContextFormatError: If the context cannot be properly formatted.
        Side Effects:
            Emits debug and warning logs describing selection outcomes and token budget usage.
        Timeout/Retry Notes:
            Executes synchronously without retries; callers must wrap invocation in their own timeout guards.
        """

        conversation_history = conversation_history or []
        memory_retrieval_results = memory_retrieval_results or []
        additional_context = additional_context or {}

        context_elements = prepare_context_elements(
            prompt=prompt,
            conversation_history=conversation_history,
            memory_retrieval_results=memory_retrieval_results,
            system_instructions=system_instructions,
            additional_context=additional_context,
            token_counter=self.token_counter,
        )

        selected_elements = select_context_elements(
            context_elements=context_elements,
            prompt_tokens=self.token_counter(prompt),
            max_tokens=self.max_tokens,
            reserved_tokens=self.reserved_tokens,
        )

        try:
            enhanced_prompt = format_context(
                prompt=prompt,
                selected_elements=selected_elements,
                conversation_history=conversation_history,
                system_instructions=system_instructions,
                strategy=self.strategy,
                format_type=self.format,
            )
        except Exception as exc:  # pragma: no cover - defensive guard
            logger.error("Error formatting context: %s", exc)
            raise InvalidContextFormatError(f"Failed to format context: {exc}") from exc

        if isinstance(enhanced_prompt, str):
            final_token_count = self.token_counter(enhanced_prompt)
        else:
            final_token_count = estimate_structured_token_count(
                enhanced_prompt,
                token_counter=self.token_counter,
            )

        max_allowed = self.max_tokens - self.reserved_tokens
        if final_token_count > max_allowed:
            logger.warning(
                "Context window exceeded: %s tokens (max: %s)",
                final_token_count,
                max_allowed,
            )
            raise ContextWindowExceededError(
                f"Enhanced prompt exceeds token limit: {final_token_count} tokens (max: {max_allowed})"
            )

        logger.info(
            "Successfully injected context. Final token count: %s (limit: %s)",
            final_token_count,
            max_allowed,
        )
        return enhanced_prompt


class ContextInjector:
    """Lightweight façade around :class:`ContextInjectionManager` for callers.

    Summary:
        Offers a narrowed surface optimised for integration points that need
        prompt enrichment without managing the lower-level assembly workflow.
    Attributes:
        manager (ContextInjectionManager): Underlying manager responsible for
            performing the injection steps.
    Side Effects:
        Delegates to the manager which logs diagnostic information regarding
        selection and formatting operations.
    Timeout/Retry Notes:
        No additional timeout logic is implemented here beyond the manager.
    """

    def __init__(self, config: ContextInjectionConfig | None = None):
        """Create a context injector with an optional explicit configuration.

        Summary:
            Resolves the configuration to use for downstream prompt injection
            and instantiates the shared :class:`ContextInjectionManager`.
        Parameters:
            config (ContextInjectionConfig | None): Caller-supplied configuration.
                When omitted, the default helper is invoked to obtain a baseline.
        Returns:
            None
        Raises:
            ValueError: Propagates validation errors raised during configuration creation.
        Side Effects:
            Delegates to the manager constructor which logs the active strategy and budgets.
        Timeout/Retry Notes:
            Instantiation is synchronous and does not define retry behaviour.
        """

        if config is None:
            config = get_default_context_injection_config()

        self.manager = ContextInjectionManager(config)

    def inject(
        self,
        prompt: str,
        conversation_history: list[dict[str, str]] | None = None,
        memory_results: list[MemoryRetrievalResult] | None = None,
        system_instructions: str | None = None,
        additional_context: dict[str, Any] | None = None,
    ) -> Union[str, dict[str, Any]]:
        """Enrich a prompt with context using the encapsulated manager.

        Summary:
            Provides a single-call wrapper that forwards payloads to the manager
            while preserving the public integration contract.
        Parameters:
            prompt (str): The original user prompt to enrich.
            conversation_history (list[dict[str, str]] | None): Prior turns represented as
                ``{"user": ..., "assistant": ...}``.
            memory_results (list[MemoryRetrievalResult] | None): Retrieved memory
                artifacts that may deepen the response.
            system_instructions (str | None): System-level directives to include.
            additional_context (dict[str, Any] | None): Arbitrary supplementary context.
        Returns:
            Union[str, dict[str, Any]]: Prompt or structured payload ready for the LLM.
        Raises:
            ContextWindowExceededError: Propagated when the manager detects a token overflow.
            InvalidContextFormatError: Propagated when formatting fails for the chosen strategy.
        Side Effects:
            Emits logs through the manager describing selection and formatting decisions.
        Timeout/Retry Notes:
            Executes synchronously without retries; wrap in caller-managed timeout scopes if needed.
        """

        return self.manager.inject_context(
            prompt=prompt,
            conversation_history=conversation_history,
            memory_retrieval_results=memory_results,
            system_instructions=system_instructions,
            additional_context=additional_context,
        )


def inject_context(
    prompt: str,
    conversation_history: list[dict[str, str]] | None = None,
    memory_results: list[MemoryRetrievalResult] | None = None,
    system_instructions: str | None = None,
    additional_context: dict[str, Any] | None = None,
    config: ContextInjectionConfig | None = None,
) -> Union[str, dict[str, Any]]:
    """Convenience wrapper to enrich a prompt with contextual information.

    Summary:
        Builds a :class:`ContextInjector` if required and delegates the heavy
        lifting while maintaining a function-oriented API.
    Parameters:
        prompt (str): The user's prompt awaiting enrichment.
        conversation_history (list[dict[str, str]] | None): Prior dialogue turns
            that may anchor the response.
        memory_results (list[MemoryRetrievalResult] | None): Retrieved memory
            snippets to surface in the final prompt.
        system_instructions (str | None): System directives and guardrails.
        additional_context (dict[str, Any] | None): Arbitrary auxiliary context.
        config (ContextInjectionConfig | None): Optional configuration override.
    Returns:
        Union[str, dict[str, Any]]: Prompt or structured payload ready for the LLM.
    Raises:
        ContextWindowExceededError: Bubble-up from the injector when token budgets are exceeded.
        InvalidContextFormatError: Propagated when formatting fails for the configured strategy.
    Side Effects:
        Emits logging via the underlying manager describing context assembly actions.
    Timeout/Retry Notes:
        Executes synchronously in-process without retries; wrap invocation if timeouts are required.
    """

    injector = ContextInjector(config)
    return injector.inject(
        prompt=prompt,
        conversation_history=conversation_history,
        memory_results=memory_results,
        system_instructions=system_instructions,
        additional_context=additional_context,
    )
