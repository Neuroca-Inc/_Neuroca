"""Context injection formatting helpers.

Purpose:
    Transform selected context elements into provider-ready prompt payloads
    according to the configured injection strategy and format.
External Dependencies:
    Uses only the Python standard library and shared context injection types.
Fallback Semantics:
    Formatting errors propagate as exceptions so callers can execute their own
    fallback or retry policies.
Timeout Strategy:
    Formatting executes synchronously and does not apply additional timeouts.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Iterable, Union

from neuroca.integration.context.injection_types import (
    ContextElement,
    ContextFormat,
    ContextInjectionStrategy,
)
from neuroca.integration.context.injection_selection import group_elements_by_source

logger = logging.getLogger(__name__)


def format_context(
    *,
    prompt: str,
    selected_elements: list[ContextElement],
    conversation_history: list[dict[str, str]],
    system_instructions: str | None,
    strategy: ContextInjectionStrategy,
    format_type: ContextFormat,
) -> Union[str, dict[str, Any]]:
    """Render selected context elements according to the configured strategy.

    Summary:
        Dispatches to strategy-specific formatting helpers and returns either a
        textual prompt or a structured payload (for ChatML-style formats).
    Parameters:
        prompt (str): The user's original prompt/question.
        selected_elements (list[ContextElement]): Context chosen for injection.
        conversation_history (list[dict[str, str]]): Recent dialogue turns used
            by strategies such as INTERLEAVE.
        system_instructions (str | None): Optional instructions appended to the
            payload when required by the strategy.
        strategy (ContextInjectionStrategy): Strategy enum describing how to
            merge context.
        format_type (ContextFormat): Provider-specific format hint (currently
            advisory but preserved for future differentiation of structured
            payloads).
    Returns:
        Union[str, dict[str, Any]]: Prompt payload ready for downstream LLM
        execution.
    Raises:
        ValueError: Raised when an unknown strategy is provided.
    Side Effects:
        None beyond logging.
    Timeout/Retry Notes:
        Not applicable.
    """

    elements_by_source = group_elements_by_source(selected_elements)

    if strategy == ContextInjectionStrategy.PREPEND:
        return format_prepend_strategy(
            prompt=prompt,
            selected_elements=selected_elements,
            system_instructions=system_instructions,
        )
    if strategy == ContextInjectionStrategy.APPEND:
        return format_append_strategy(prompt=prompt, selected_elements=selected_elements)
    if strategy == ContextInjectionStrategy.INTERLEAVE:
        return format_interleave_strategy(
            prompt=prompt,
            selected_elements=selected_elements,
            conversation_history=conversation_history,
        )
    if strategy == ContextInjectionStrategy.STRUCTURED:
        return format_structured_strategy(
            prompt=prompt,
            elements_by_source=elements_by_source,
            system_instructions=system_instructions,
            format_type=format_type,
        )

    logger.warning("Unrecognized strategy %s; defaulting to PREPEND", strategy)
    return format_prepend_strategy(
        prompt=prompt,
        selected_elements=selected_elements,
        system_instructions=system_instructions,
    )


def format_prepend_strategy(
    *,
    prompt: str,
    selected_elements: Iterable[ContextElement],
    system_instructions: str | None,
) -> str:
    """Prepend selected context ahead of the user's prompt.

    Summary:
        Builds a conversational preamble with optional system instructions
        followed by the user's prompt and an assistant cue.
    Parameters:
        prompt (str): The user's original prompt.
        selected_elements (Iterable[ContextElement]): Elements to prepend.
        system_instructions (str | None): High-priority instructions when
            available.
    Returns:
        str: Formatted prompt string.
    Raises:
        None.
    Side Effects:
        None beyond string assembly.
    Timeout/Retry Notes:
        Not applicable.
    """

    formatted_context = ""

    if system_instructions:
        formatted_context += f"System: {system_instructions}\n\n"

    for element in selected_elements:
        if element.source == "system_instructions":
            formatted_context += f"System instructions: {element.content}\n\n"
        elif element.source == "conversation_history" or element.source not in {
            "memory_retrieval",
            "additional_context",
        }:
            formatted_context += f"{element.content}\n\n"
        elif element.source == "memory_retrieval":
            memory_type = element.metadata.get("memory_type", "Memory")
            formatted_context += f"Relevant {memory_type}: {element.content}\n\n"
        else:
            context_key = element.metadata.get("context_key", "Context")
            formatted_context += f"{context_key}: {element.content}\n\n"

    formatted_context += f"User: {prompt}\n\nAssistant:"
    return formatted_context


def format_append_strategy(
    *,
    prompt: str,
    selected_elements: Iterable[ContextElement],
) -> str:
    """Append context after the user's prompt with labelled sections.

    Summary:
        Presents the prompt first and appends clearly labelled context blocks,
        concluding with an assistant cue.
    Parameters:
        prompt (str): The user's original prompt.
        selected_elements (Iterable[ContextElement]): Elements appended after
            the prompt.
    Returns:
        str: Formatted prompt string.
    Raises:
        None.
    Side Effects:
        None.
    Timeout/Retry Notes:
        Not applicable.
    """

    formatted_context = f"User: {prompt}\n\n"

    if selected_elements:
        formatted_context += "Additional context:\n"
        for element in selected_elements:
            if element.source == "system_instructions":
                formatted_context += f"System instructions: {element.content}\n\n"
            elif element.source == "conversation_history":
                formatted_context += f"Previous conversation: {element.content}\n\n"
            elif element.source == "memory_retrieval":
                memory_type = element.metadata.get("memory_type", "Memory")
                formatted_context += f"Relevant {memory_type}: {element.content}\n\n"
            elif element.source == "additional_context":
                context_key = element.metadata.get("context_key", "Context")
                formatted_context += f"{context_key}: {element.content}\n\n"
            else:
                formatted_context += f"{element.content}\n\n"

    formatted_context += "Assistant:"
    return formatted_context


def format_interleave_strategy(
    *,
    prompt: str,
    selected_elements: list[ContextElement],
    conversation_history: list[dict[str, str]],
) -> str:
    """Interleave context elements with the existing conversation turns.

    Summary:
        Replays the conversation history while weaving in additional context at
        fixed intervals, concluding with the user's prompt and assistant cue.
    Parameters:
        prompt (str): The user's original prompt.
        selected_elements (list[ContextElement]): Elements to interleave.
        conversation_history (list[dict[str, str]]): Dialogue history.
    Returns:
        str: Formatted prompt string.
    Raises:
        None.
    Side Effects:
        None.
    Timeout/Retry Notes:
        Not applicable.
    """

    non_conversation_elements = [
        element for element in selected_elements if element.source != "conversation_history"
    ]
    conversation_elements = [
        element for element in selected_elements if element.source == "conversation_history"
    ]

    system_elements = [element for element in selected_elements if element.source == "system_instructions"]
    formatted_context = "".join(
        f"System: {element.content}\n\n" for element in system_elements
    )
    for index, turn in enumerate(conversation_history):
        if "user" in turn:
            formatted_context += f"User: {turn['user']}\n\n"
        if "assistant" in turn:
            formatted_context += f"Assistant: {turn['assistant']}\n\n"

        if index % 2 == 1 and non_conversation_elements:
            element = non_conversation_elements.pop(0)
            formatted_context += _format_bracketed_context(element)
            if not non_conversation_elements:
                break

    if not conversation_history and conversation_elements:
        for element in conversation_elements:
            formatted_context += f"[Conversation recap: {element.content}]\n\n"

    for element in non_conversation_elements:
        formatted_context += _format_bracketed_context(element)

    formatted_context += f"User: {prompt}\n\nAssistant:"
    return formatted_context


def format_structured_strategy(
    *,
    prompt: str,
    elements_by_source: dict[str, list[ContextElement]],
    system_instructions: str | None,
    format_type: ContextFormat,
) -> dict[str, Any]:
    """Render context as a structured payload (e.g., ChatML message list).

    Summary:
        Produces a dictionary with a ``messages`` array compatible with
        structured chat APIs. ``format_type`` is currently advisory and kept for
        future differentiation between providers.
    Parameters:
        prompt (str): The user's original prompt.
        elements_by_source (dict[str, list[ContextElement]]): Elements keyed by
            source.
        system_instructions (str | None): Optional system instructions to merge.
        format_type (ContextFormat): Provider hint (currently unused but
            reserved for future format-specific adjustments).
    Returns:
        dict[str, Any]: Structured payload containing ordered messages.
    Raises:
        None.
    Side Effects:
        None.
    Timeout/Retry Notes:
        Not applicable.
    """

    messages: list[dict[str, str]] = []

    if system_instructions or "system_instructions" in elements_by_source:
        system_content = system_instructions or ""
        for element in elements_by_source.get("system_instructions", []):
            system_content += f"{element.content}\n\n"
        messages.append({"role": "system", "content": system_content.strip()})

    if "memory_retrieval" in elements_by_source:
        memory_content = "Relevant information from memory:\n\n"
        for element in elements_by_source["memory_retrieval"]:
            memory_type = element.metadata.get("memory_type", "Memory")
            memory_content += f"- {memory_type}: {element.content}\n\n"
        messages.append({"role": "system", "content": memory_content.strip()})

    if "additional_context" in elements_by_source:
        context_content = "Additional context:\n\n"
        for element in elements_by_source["additional_context"]:
            context_key = element.metadata.get("context_key", "Context")
            context_content += f"- {context_key}: {element.content}\n\n"
        messages.append({"role": "system", "content": context_content.strip()})

    if "conversation_history" in elements_by_source:
        conversation_elements = sorted(
            elements_by_source["conversation_history"],
            key=lambda element: element.metadata.get("turn_index", 0) if element.metadata else 0,
        )
        for element in conversation_elements:
            content = element.content
            if content.startswith("User: ") and "Assistant: " in content:
                user_content, assistant_content = content.split("Assistant: ", 1)
                user_content = user_content.replace("User: ", "", 1).strip()
                messages.extend(
                    (
                        {"role": "user", "content": user_content},
                        {
                            "role": "assistant",
                            "content": assistant_content.strip(),
                        },
                    )
                )
            elif content.startswith("User: "):
                messages.append({"role": "user", "content": content.replace("User: ", "", 1).strip()})
            elif content.startswith("Assistant: "):
                messages.append({"role": "assistant", "content": content.replace("Assistant: ", "", 1).strip()})

    messages.append({"role": "user", "content": prompt})
    return {"messages": messages}


def estimate_structured_token_count(
    structured_prompt: dict[str, Any],
    token_counter: Callable[[str], int],
    overhead_per_message: int = 4,
) -> int:
    """Estimate token usage for a structured prompt payload.

    Summary:
        Applies a best-effort heuristic by summing token counts for each message
        plus a constant overhead per message to approximate metadata tokens.
    Parameters:
        structured_prompt (dict[str, Any]): Structured payload generated by
            :func:`format_structured_strategy`.
        token_counter (Callable[[str], int]): Token counting function injected by
            the manager.
        overhead_per_message (int): Approximate overhead for message metadata.
    Returns:
        int: Estimated token count for the structured payload.
    Raises:
        None.
    Side Effects:
        None beyond computation.
    Timeout/Retry Notes:
        Not applicable.
    """

    total_tokens = 0
    for message in structured_prompt.get("messages", []):
        if content := message.get("content", ""):
            total_tokens += token_counter(content)
        total_tokens += overhead_per_message
    return total_tokens


def _format_bracketed_context(element: ContextElement) -> str:
    """Render a non-conversation context element in bracketed form.

    Summary:
        Helper for :func:`format_interleave_strategy` that produces consistent
        bracketed annotations for memory and auxiliary context items.
    Parameters:
        element (ContextElement): Context element to format.
    Returns:
        str: Bracketed context string with trailing newline characters.
    Raises:
        None.
    Side Effects:
        None.
    Timeout/Retry Notes:
        Not applicable.
    """

    if element.source == "memory_retrieval":
        memory_type = element.metadata.get("memory_type", "Memory")
        return f"[Relevant {memory_type}: {element.content}]\n\n"
    if element.source == "additional_context":
        context_key = element.metadata.get("context_key", "Context")
        return f"[{context_key}: {element.content}]\n\n"
    return f"[Context: {element.content}]\n\n"
