"""
Context injection configuration definitions.

Purpose:
    Provide strongly typed configuration objects and helpers for the prompt
    context injection subsystem so higher layers can depend on validated
    settings instead of loose dictionaries.
External Dependencies:
    None. This module relies exclusively on the Python standard library.
Fallback Semantics:
    When no explicit configuration is provided, callers should use
    `get_default_context_injection_config()` which returns a conservative
    configuration suitable for single-tenant demos.
Timeout Strategy:
    Configuration loading is non-blocking; no timeout management is required
    in this module. Runtime callers are expected to enforce their own limits.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ContextInjectionConfig:
    """Immutable configuration values for context injection routines.

    Summary:
        Encapsulates the tunable parameters that govern how prompts are
        expanded with contextual information before being sent to an LLM.
    Parameters:
        max_context_window_tokens (int): Upper bound on the total tokens
            allowed for the assembled prompt plus injected context.
        reserved_tokens_for_response (int): Allocation reserved for the model's
            response when evaluating the token budget.
        context_format (str): Identifier of the downstream provider format
            (e.g. ``"openai"`` or ``"anthropic"``).
        injection_strategy (str): Strategy keyword indicating how context is
            merged with the base prompt (prepend, append, interleave, etc.).
        max_memory_elements (int): Optional guard for how many memory elements
            may be considered per invocation.
        max_history_turns (int): Limit on how many conversational turns are
            revisited when preparing history context.
    Returns:
        ContextInjectionConfig: Configured dataclass instance used by the
        context injection manager.
    Raises:
        ValueError: Raised by dataclass validation when supplied values are
        inconsistent (e.g. non-positive token budgets).
    Side Effects:
        None. Instances are pure data objects.
    Timeout/Retry Notes:
        Not applicable. Construction is immediate and does not perform I/O.
    """

    max_context_window_tokens: int = 4096
    reserved_tokens_for_response: int = 512
    context_format: str = "openai"
    injection_strategy: str = "prepend"
    max_memory_elements: int = 16
    max_history_turns: int = 10

    def __post_init__(self) -> None:
        """Validate core invariants for the configuration payload.

        Summary:
            Enforces basic invariants so runtime consumers can avoid defensive
            checks on every call site.
        Parameters:
            None
        Returns:
            None
        Raises:
            ValueError: If numerical budgets are non-positive values.
        Side Effects:
            None. Validation relies on local comparisons only.
        Timeout/Retry Notes:
            Not applicable; execution is CPU-local and instantaneous.
        """
        if self.max_context_window_tokens <= 0:
            raise ValueError("max_context_window_tokens must be a positive integer")
        if self.reserved_tokens_for_response < 0:
            raise ValueError("reserved_tokens_for_response cannot be negative")
        if self.max_memory_elements <= 0:
            raise ValueError("max_memory_elements must be a positive integer")
        if self.max_history_turns <= 0:
            raise ValueError("max_history_turns must be a positive integer")


def get_default_context_injection_config() -> ContextInjectionConfig:
    """Build the default context injection configuration for callers.

    Summary:
        Supplies a conservative default configuration that works across the
        supported prompt formatting strategies without exhausting context
        budgets during demos or smoke tests.
    Parameters:
        None
    Returns:
        ContextInjectionConfig: Immutable configuration populated with default
        values aligned with the hosted demo profile.
    Raises:
        None
    Side Effects:
        None. The dataclass instance is constructed in memory only.
    Timeout/Retry Notes:
        Not applicable. The function executes synchronously without external
        dependencies or retry semantics.
    """

    return ContextInjectionConfig()
