"""Context injection element preparation and selection helpers.

Purpose:
    Provide pure functions that construct context element collections from raw
    inputs and apply token-budget-based selection logic for downstream
    formatting.
External Dependencies:
    Standard library only. No CLI tools or network requests are invoked.
Fallback Semantics:
    Callers are expected to supply validated inputs. The helpers surface issues
    via standard exceptions rather than attempting silent fallbacks.
Timeout Strategy:
    Not applicable; computation is synchronous and CPU-bound.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Callable, Iterable

from neuroca.integration.context.injection_types import ContextElement, ContextPriority

logger = logging.getLogger(__name__)


def prepare_context_elements(
    *,
    prompt: str,
    conversation_history: Iterable[dict[str, str]] | None,
    memory_retrieval_results: Iterable[Any] | None,
    system_instructions: str | None,
    additional_context: dict[str, Any] | None,
    token_counter: Callable[[str], int],
) -> list[ContextElement]:
    """Build a list of candidate context elements from upstream inputs.

    Summary:
        Converts raw conversation turns, memory retrieval artefacts, system
        instructions, and ad-hoc context dictionaries into ``ContextElement``
        instances annotated with priorities and token counts.
    Parameters:
        prompt (str): The original user prompt (not directly used but retained
            for parity with future heuristics).
        conversation_history (Iterable[dict[str, str]] | None): Ordered
            history of dialogue turns.
        memory_retrieval_results (Iterable[Any] | None): Items returned from
            memory retrieval subsystems.
        system_instructions (str | None): Global system message to prioritise.
        additional_context (dict[str, Any] | None): Arbitrary context map to
            fold into the injection set.
        token_counter (Callable[[str], int]): Function used to estimate token
            footprints for textual content.
    Returns:
        list[ContextElement]: All candidate elements prior to selection.
    Raises:
        TypeError: Propagated if ``token_counter`` is not callable or produces
            non-integer results.
    Side Effects:
        Emits debug logs describing the number of prepared elements.
    Timeout/Retry Notes:
        Not applicable.
    """

    conversation_history = list(conversation_history or [])
    memory_retrieval_results = list(memory_retrieval_results or [])
    additional_context = additional_context or {}

    context_elements: list[ContextElement] = []

    if system_instructions:
        context_elements.append(
            ContextElement(
                content=system_instructions,
                source="system_instructions",
                priority=ContextPriority.CRITICAL,
                token_count=token_counter(system_instructions),
            )
        )

    for index, turn in enumerate(conversation_history):
        if index >= len(conversation_history) - 3:
            priority = ContextPriority.HIGH
        elif index >= len(conversation_history) - 6:
            priority = ContextPriority.MEDIUM
        else:
            priority = ContextPriority.LOW

        if "user" in turn and "assistant" in turn:
            content = f"User: {turn['user']}\nAssistant: {turn['assistant']}"
        elif "user" in turn:
            content = f"User: {turn['user']}"
        elif "assistant" in turn:
            content = f"Assistant: {turn['assistant']}"
        else:
            content = str(turn)

        context_elements.append(
            ContextElement(
                content=content,
                source="conversation_history",
                priority=priority,
                token_count=token_counter(content),
                metadata={"turn_index": index},
            )
        )

    for result in memory_retrieval_results:
        priority = _derive_memory_priority(result)
        content = getattr(result, "content", None) or str(result)

        metadata: dict[str, Any] = {}
        for attr in ("memory_type", "timestamp", "relevance_score"):
            if hasattr(result, attr):
                metadata[attr] = getattr(result, attr)

        context_elements.append(
            ContextElement(
                content=content,
                source="memory_retrieval",
                priority=priority,
                token_count=token_counter(content),
                metadata=metadata,
            )
        )

    for key, value in additional_context.items():
        if isinstance(value, (str, int, float, bool)):
            content = f"{key}: {value}"
        else:
            content = json.dumps(value)

        context_elements.append(
            ContextElement(
                content=content,
                source="additional_context",
                priority=ContextPriority.MEDIUM,
                token_count=token_counter(content),
                metadata={"context_key": key},
            )
        )

    logger.debug("Prepared %d context elements", len(context_elements))
    return context_elements


def select_context_elements(
    *,
    context_elements: list[ContextElement],
    prompt_tokens: int,
    max_tokens: int,
    reserved_tokens: int,
) -> list[ContextElement]:
    """Choose context elements that fit within the configured token budget.

    Summary:
        Sorts elements by priority, keeps CRITICAL entries unconditionally, and
        then adds lower-priority items while respecting the available token window.
    Parameters:
        context_elements (list[ContextElement]): Candidate elements created by
            :func:`prepare_context_elements`.
        prompt_tokens (int): Token count of the original prompt.
        max_tokens (int): Maximum allowed tokens for prompt plus context.
        reserved_tokens (int): Token budget reserved for the model's response.
    Returns:
        list[ContextElement]: Elements selected for injection.
    Raises:
        ValueError: If ``max_tokens`` minus ``reserved_tokens`` minus
            ``prompt_tokens`` is negative, indicating an impossible budget.
    Side Effects:
        Emits info/debug logs describing selection outcomes.
    Timeout/Retry Notes:
        Not applicable.
    """

    available_tokens = max_tokens - reserved_tokens - prompt_tokens
    if available_tokens < 0:
        raise ValueError(
            "Available token budget is negative. Check max_tokens, reserved_tokens, and prompt length."
        )

    sorted_elements = sorted(context_elements, key=lambda element: element.priority.value)
    selected_elements: list[ContextElement] = []
    used_tokens = 0

    for element in sorted_elements:
        if element.priority == ContextPriority.CRITICAL:
            selected_elements.append(element)
            used_tokens += element.token_count
            continue

        if used_tokens + element.token_count <= available_tokens:
            selected_elements.append(element)
            used_tokens += element.token_count
        else:
            logger.debug(
                "Skipping context element due to token limits: %s (priority=%s, tokens=%s)",
                element.source,
                element.priority.name,
                element.token_count,
            )

    logger.info(
        "Selected %d/%d context elements using %d/%d available tokens",
        len(selected_elements),
        len(context_elements),
        used_tokens,
        available_tokens,
    )
    return selected_elements


def group_elements_by_source(elements: Iterable[ContextElement]) -> dict[str, list[ContextElement]]:
    """Group context elements by their ``source`` attribute.

    Summary:
        Builds a dictionary keyed by source (e.g., ``"conversation_history"``)
        to simplify downstream formatting logic.
    Parameters:
        elements (Iterable[ContextElement]): Selected context elements.
    Returns:
        dict[str, list[ContextElement]]: Mapping of sources to element lists.
    Raises:
        None.
    Side Effects:
        None beyond allocating the returned dictionary.
    Timeout/Retry Notes:
        Not applicable.
    """

    grouped: dict[str, list[ContextElement]] = {}
    for element in elements:
        grouped.setdefault(element.source, []).append(element)
    return grouped


def _derive_memory_priority(result: Any) -> ContextPriority:
    """Calculate priority for a memory retrieval result based on relevance.

    Summary:
        Inspects the ``relevance_score`` attribute when available to map results
        into the configured priority buckets.
    Parameters:
        result (Any): Memory retrieval artefact potentially exposing
            ``relevance_score``.
    Returns:
        ContextPriority: Priority bucket.
    Raises:
        None.
    Side Effects:
        None.
    Timeout/Retry Notes:
        Not applicable.
    """

    relevance = getattr(result, "relevance_score", None)
    if relevance is None:
        return ContextPriority.MEDIUM
    if relevance > 0.8:
        return ContextPriority.HIGH
    if relevance > 0.6:
        return ContextPriority.MEDIUM
    return ContextPriority.LOW
