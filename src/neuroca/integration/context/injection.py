"""
Context injection orchestration for NeuroCognitive Architecture.

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

import json
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional, Union

from neuroca.config.context_injection import ContextInjectionConfig, get_default_context_injection_config
from neuroca.core.exceptions import ContextWindowExceededError, InvalidContextFormatError
from neuroca.memory.models import MemoryRetrievalResult

# Configure logger
logger = logging.getLogger(__name__)


class ContextPriority(Enum):
    """
    Priority buckets describing the relative importance of context elements.

    Summary:
        Encodes the ordering semantics used during selection so that higher
        priority entries are retained when token budgets require trimming.
    Side Effects:
        None. Enum usage is read-only.
    Timeout/Retry Notes:
        Not applicable.
    """
    CRITICAL = 0
    HIGH = 1
    MEDIUM = 2
    LOW = 3
    BACKGROUND = 4


@dataclass
class ContextElement:
    """
    Data carrier for a single context element slated for injection.

    Summary:
        Captures the textual content, provenance metadata, and precomputed token
        estimate used during prioritisation and formatting.
    Attributes:
        content (str): The human-readable text to inject.
        source (str): Logical origin such as ``"working_memory"`` or ``"conversation_history"``.
        priority (ContextPriority): Priority bucket relative to other elements.
        token_count (int): Estimated token footprint for budget calculations.
        metadata (dict[str, Any]): Optional structured metadata describing the element.
    Side Effects:
        None. Instances only store data.
    Timeout/Retry Notes:
        Not applicable.
    """
    content: str
    source: str  # e.g., "working_memory", "episodic_memory", "semantic_memory"
    priority: ContextPriority
    token_count: int
    metadata: dict[str, Any] = None
    
    def __post_init__(self) -> None:
        """
        Normalise metadata container after dataclass initialisation.

        Summary:
            Guarantees that downstream consumers always interact with a dictionary
            even when callers omit metadata during construction.
        Parameters:
            None
        Returns:
            None
        Raises:
            None
        Side Effects:
            Mutates ``self.metadata`` to an empty dictionary when ``None`` is supplied.
        Timeout/Retry Notes:
            Not applicable.
        """
        if self.metadata is None:
            self.metadata = {}


class ContextFormat(Enum):
    """
    Supported formatting styles mapped to downstream LLM providers.

    Summary:
        Signals how the assembled context should be serialized so the provider
        receives a compatible payload representation.
    Side Effects:
        None. Enumeration values are constants.
    Timeout/Retry Notes:
        Not applicable.
    """
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    CUSTOM = "custom"


class ContextInjectionStrategy(Enum):
    """
    Strategies describing how context is threaded into the prompt template.

    Summary:
        Enumerates merge approaches (prepend, append, interleave, structured) to
        drive formatting logic in the injection manager.
    Side Effects:
        None. Values are pure metadata.
    Timeout/Retry Notes:
        Not applicable.
    """
    PREPEND = "prepend"  # Add context before the prompt
    APPEND = "append"    # Add context after the prompt
    INTERLEAVE = "interleave"  # Mix context with conversation turns
    STRUCTURED = "structured"  # Use a structured format (e.g., JSON)


class ContextInjectionManager:
    """
    Coordinate context assembly and injection for outbound prompts.

    Summary:
        Wraps helper routines that prepare, select, and format contextual
        elements prior to dispatching a prompt to an LLM provider.
    Attributes:
        config (ContextInjectionConfig): Resolved configuration payload.
        max_tokens (int): Maximum tokens allowed for the final prompt plus context.
        reserved_tokens (int): Tokens reserved for the LLM response window.
        format (ContextFormat): Provider-specific formatting directive.
        strategy (ContextInjectionStrategy): Strategy describing how context is merged.
    Side Effects:
        Emits structured debug/info logs describing prioritisation, selection,
        and formatting behaviour.
    Timeout/Retry Notes:
        No explicit timeout or retry handling; callers should wrap invocation in
        application-level timeout controls when necessary.
    """
    
    def __init__(self, config: ContextInjectionConfig):
        """
        Initialise the context injection manager with validated configuration.

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
        self.token_counter = self._get_token_counter()
        logger.debug(f"Initialized ContextInjectionManager with format={self.format.value}, "
                    f"strategy={self.strategy.value}, max_tokens={self.max_tokens}")
    
    def _get_token_counter(self):
        """
        Returns the appropriate token counting function based on configuration.
        
        Different LLMs may have different tokenization methods, so this allows
        for flexibility in how tokens are counted.
        
        Returns:
            A function that counts tokens in a string
        """
        # This is a placeholder - in production code, you would use the actual tokenizer
        return lambda text: len(text.split())
    
    def inject_context(
        self,
        prompt: str,
        conversation_history: list[dict[str, str]] = None,
        memory_retrieval_results: list[MemoryRetrievalResult] = None,
        system_instructions: str = None,
        additional_context: dict[str, Any] = None
    ) -> Union[str, dict[str, Any]]:
        """
        Inject relevant context into the prompt based on available information.
        
        Args:
            prompt: The user's current prompt/query
            conversation_history: Previous conversation turns
            memory_retrieval_results: Results from memory retrieval systems
            system_instructions: System-level instructions for the LLM
            additional_context: Any additional context to consider
            
        Returns:
            Enhanced prompt with injected context, formatted appropriately for the target LLM
            
        Raises:
            ContextWindowExceededError: If the resulting context exceeds the maximum token limit
            InvalidContextFormatError: If the context cannot be properly formatted
        Side Effects:
            Emits debug and warning logs describing selection outcomes and token budget usage.
        Timeout/Retry Notes:
            Executes synchronously without retries; callers must wrap in their own timeout guards.
        """
        logger.debug(f"Injecting context for prompt: {prompt[:50]}...")

        # Initialize with empty lists if None
        conversation_history = conversation_history or []
        memory_retrieval_results = memory_retrieval_results or []
        additional_context = additional_context or {}

        # 1. Prepare context elements from various sources
        context_elements = self._prepare_context_elements(
            prompt=prompt,
            conversation_history=conversation_history,
            memory_retrieval_results=memory_retrieval_results,
            system_instructions=system_instructions,
            additional_context=additional_context
        )

        # 2. Prioritize and select context elements to fit within token limits
        selected_elements = self._select_context_elements(
            context_elements=context_elements,
            prompt_tokens=self.token_counter(prompt)
        )

        # 3. Format the selected context elements according to the chosen strategy
        try:
            enhanced_prompt = self._format_context(
                prompt=prompt,
                selected_elements=selected_elements,
                conversation_history=conversation_history,
                system_instructions=system_instructions
            )
        except Exception as e:
            logger.error(f"Error formatting context: {str(e)}")
            raise InvalidContextFormatError(f"Failed to format context: {str(e)}") from e

        # 4. Verify the final token count is within limits
        final_token_count = self.token_counter(enhanced_prompt) if isinstance(enhanced_prompt, str) else \
                               self._estimate_structured_token_count(enhanced_prompt)

        if final_token_count > self.max_tokens - self.reserved_tokens:
            logger.warning(f"Context window exceeded: {final_token_count} tokens (max: {self.max_tokens - self.reserved_tokens})")
            raise ContextWindowExceededError(
                f"Enhanced prompt exceeds token limit: {final_token_count} tokens "
                f"(max: {self.max_tokens - self.reserved_tokens})"
            )

        logger.info(f"Successfully injected context. Final token count: {final_token_count}")
        return enhanced_prompt
    
    def _prepare_context_elements(
        self,
        prompt: str,
        conversation_history: list[dict[str, str]],
        memory_retrieval_results: list[MemoryRetrievalResult],
        system_instructions: Optional[str],
        additional_context: dict[str, Any]
    ) -> list[ContextElement]:
        """
        Prepare context elements from various sources.
        
        Args:
            prompt: The user's current prompt/query
            conversation_history: Previous conversation turns
            memory_retrieval_results: Results from memory retrieval systems
            system_instructions: System-level instructions for the LLM
            additional_context: Any additional context to consider
            
        Returns:
            List of ContextElement objects representing all potential context
        """
        context_elements = []
        
        # Add system instructions as highest priority if present
        if system_instructions:
            context_elements.append(ContextElement(
                content=system_instructions,
                source="system_instructions",
                priority=ContextPriority.CRITICAL,
                token_count=self.token_counter(system_instructions)
            ))
        
        # Add conversation history
        for i, turn in enumerate(conversation_history):
            # More recent turns get higher priority
            priority = ContextPriority.HIGH if i >= len(conversation_history) - 3 else \
                      ContextPriority.MEDIUM if i >= len(conversation_history) - 6 else \
                      ContextPriority.LOW
            
            # Format the conversation turn
            if 'user' in turn and 'assistant' in turn:
                content = f"User: {turn['user']}\nAssistant: {turn['assistant']}"
            elif 'user' in turn:
                content = f"User: {turn['user']}"
            elif 'assistant' in turn:
                content = f"Assistant: {turn['assistant']}"
            else:
                content = str(turn)
            
            context_elements.append(ContextElement(
                content=content,
                source="conversation_history",
                priority=priority,
                token_count=self.token_counter(content),
                metadata={"turn_index": i}
            ))
        
        # Add memory retrieval results
        for result in memory_retrieval_results:
            # Determine priority based on relevance score
            if hasattr(result, 'relevance_score') and result.relevance_score is not None:
                if result.relevance_score > 0.8:
                    priority = ContextPriority.HIGH
                elif result.relevance_score > 0.6:
                    priority = ContextPriority.MEDIUM
                else:
                    priority = ContextPriority.LOW
            else:
                priority = ContextPriority.MEDIUM
            
            # Format the memory content
            if hasattr(result, 'content') and result.content:
                content = result.content
            else:
                content = str(result)
            
            # Add metadata about memory type if available
            metadata = {}
            if hasattr(result, 'memory_type'):
                metadata['memory_type'] = result.memory_type
            if hasattr(result, 'timestamp'):
                metadata['timestamp'] = result.timestamp
            if hasattr(result, 'relevance_score'):
                metadata['relevance_score'] = result.relevance_score
            
            context_elements.append(ContextElement(
                content=content,
                source="memory_retrieval",
                priority=priority,
                token_count=self.token_counter(content),
                metadata=metadata
            ))
        
        # Add additional context
        for key, value in additional_context.items():
            content = f"{key}: {value}" if isinstance(value, (str, int, float, bool)) else json.dumps(value)
            context_elements.append(ContextElement(
                content=content,
                source="additional_context",
                priority=ContextPriority.MEDIUM,
                token_count=self.token_counter(content),
                metadata={"context_key": key}
            ))
        
        logger.debug(f"Prepared {len(context_elements)} context elements")
        return context_elements
    
    def _select_context_elements(
        self,
        context_elements: list[ContextElement],
        prompt_tokens: int
    ) -> list[ContextElement]:
        """
        Select which context elements to include based on priority and token limits.
        
        Args:
            context_elements: List of all potential context elements
            prompt_tokens: Number of tokens in the original prompt
            
        Returns:
            List of selected context elements that fit within token limits
        """
        # Sort elements by priority (CRITICAL first, BACKGROUND last)
        sorted_elements = sorted(context_elements, key=lambda x: x.priority.value)
        
        # Calculate available tokens
        available_tokens = self.max_tokens - self.reserved_tokens - prompt_tokens
        
        # Select elements until we run out of space
        selected_elements = []
        current_tokens = 0
        
        for element in sorted_elements:
            # Always include CRITICAL elements
            if element.priority == ContextPriority.CRITICAL:
                selected_elements.append(element)
                current_tokens += element.token_count
                continue
                
            # For other priorities, check if we have space
            if current_tokens + element.token_count <= available_tokens:
                selected_elements.append(element)
                current_tokens += element.token_count
            else:
                # If we're out of space, skip this element
                logger.debug(f"Skipping context element due to token limits: {element.source} "
                           f"(priority: {element.priority.name}, tokens: {element.token_count})")
        
        logger.info(f"Selected {len(selected_elements)}/{len(context_elements)} context elements "
                   f"using {current_tokens}/{available_tokens} available tokens")
        
        return selected_elements
    
    def _format_context(
        self,
        prompt: str,
        selected_elements: list[ContextElement],
        conversation_history: list[dict[str, str]],
        system_instructions: Optional[str]
    ) -> Union[str, dict[str, Any]]:
        """
        Format the selected context elements according to the chosen strategy and format.
        
        Args:
            prompt: The user's current prompt/query
            selected_elements: The selected context elements to include
            conversation_history: Previous conversation turns
            system_instructions: System-level instructions for the LLM
            
        Returns:
            Formatted prompt with injected context, either as a string or structured object
        """
        # Group elements by source for easier handling
        elements_by_source = {}
        for element in selected_elements:
            if element.source not in elements_by_source:
                elements_by_source[element.source] = []
            elements_by_source[element.source].append(element)
        
        # Format based on the selected strategy
        if self.strategy == ContextInjectionStrategy.PREPEND:
            return self._format_prepend_strategy(prompt, selected_elements, system_instructions)
        elif self.strategy == ContextInjectionStrategy.APPEND:
            return self._format_append_strategy(prompt, selected_elements)
        elif self.strategy == ContextInjectionStrategy.INTERLEAVE:
            return self._format_interleave_strategy(prompt, selected_elements, conversation_history)
        elif self.strategy == ContextInjectionStrategy.STRUCTURED:
            return self._format_structured_strategy(prompt, elements_by_source, system_instructions)
        else:
            # Default to prepend if strategy is not recognized
            logger.warning(f"Unrecognized strategy {self.strategy}, defaulting to PREPEND")
            return self._format_prepend_strategy(prompt, selected_elements, system_instructions)
    
    def _format_prepend_strategy(
        self,
        prompt: str,
        selected_elements: list[ContextElement],
        system_instructions: Optional[str]
    ) -> str:
        """
        Format context by prepending it to the prompt.
        
        Args:
            prompt: The user's current prompt/query
            selected_elements: The selected context elements to include
            system_instructions: System-level instructions for the LLM
            
        Returns:
            Formatted prompt with context prepended
        """
        # Start with system instructions if present and not already in selected elements
        formatted_context = ""
        system_in_elements = any(e.source == "system_instructions" for e in selected_elements)

        if system_instructions and not system_in_elements:
            formatted_context += f"System: {system_instructions}\n\n"

        # Add other context elements
        for element in selected_elements:
            # Skip system instructions if we already added them
            if element.source == "system_instructions" and formatted_context.startswith("System:"):
                continue

            # Format based on source
            if element.source == "system_instructions":
                formatted_context += f"System: {element.content}\n\n"
            elif element.source == "conversation_history" or element.source not in [
                "memory_retrieval",
                "additional_context",
            ]:
                formatted_context += f"{element.content}\n\n"
            elif element.source == "memory_retrieval":
                memory_type = element.metadata.get("memory_type", "Memory")
                formatted_context += f"Relevant {memory_type}: {element.content}\n\n"
            else:
                context_key = element.metadata.get("context_key", "Context")
                formatted_context += f"{context_key}: {element.content}\n\n"
        # Add the user's prompt
        formatted_context += f"User: {prompt}\n\nAssistant:"

        return formatted_context
    
    def _format_append_strategy(
        self,
        prompt: str,
        selected_elements: list[ContextElement]
    ) -> str:
        """
        Format context by appending it after the prompt.
        
        Args:
            prompt: The user's current prompt/query
            selected_elements: The selected context elements to include
            
        Returns:
            Formatted prompt with context appended
        """
        # Start with the user's prompt
        formatted_context = f"User: {prompt}\n\n"
        
        # Add context elements
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
    
    def _format_interleave_strategy(
        self,
        prompt: str,
        selected_elements: list[ContextElement],
        conversation_history: list[dict[str, str]]
    ) -> str:
        """
        Format context by interleaving it with conversation history.
        
        Args:
            prompt: The user's current prompt/query
            selected_elements: The selected context elements to include
            conversation_history: Previous conversation turns
            
        Returns:
            Formatted prompt with interleaved context
        """
        # Filter out conversation history elements from selected_elements
        non_conversation_elements = [e for e in selected_elements 
                                    if e.source != "conversation_history"]
        
        # Get conversation history elements captured during selection
        conversation_elements = [
            element for element in selected_elements if element.source == "conversation_history"
        ]
        
        # Build conversation with interleaved context
        formatted_context = ""
        
        # Add system instructions first if present
        system_elements = [e for e in selected_elements if e.source == "system_instructions"]
        if system_elements:
            for element in system_elements:
                formatted_context += f"System: {element.content}\n\n"
        
        # Add conversation history with interleaved context
        for i, turn in enumerate(conversation_history):
            # Add the conversation turn
            if 'user' in turn:
                formatted_context += f"User: {turn['user']}\n\n"
            if 'assistant' in turn:
                formatted_context += f"Assistant: {turn['assistant']}\n\n"
            
            # After certain turns, add relevant context
            if i % 2 == 1 and non_conversation_elements:  # Add after assistant responses
                # Take the next context element
                element = non_conversation_elements.pop(0)
                
                if element.source == "memory_retrieval":
                    memory_type = element.metadata.get("memory_type", "Memory")
                    formatted_context += f"[Relevant {memory_type}: {element.content}]\n\n"
                elif element.source == "additional_context":
                    context_key = element.metadata.get("context_key", "Context")
                    formatted_context += f"[{context_key}: {element.content}]\n\n"
                else:
                    formatted_context += f"[Context: {element.content}]\n\n"
                
                # If we've used all non-conversation elements, break out
                if not non_conversation_elements:
                    break
        
        if not conversation_history and conversation_elements:
            for element in conversation_elements:
                formatted_context += f"[Conversation recap: {element.content}]\\n\\n"

"

        # Add any remaining context elements
        for element in non_conversation_elements:

            if element.source == "memory_retrieval":
                memory_type = element.metadata.get("memory_type", "Memory")
                formatted_context += f"[Relevant {memory_type}: {element.content}]\n\n"
            elif element.source == "additional_context":
                context_key = element.metadata.get("context_key", "Context")
                formatted_context += f"[{context_key}: {element.content}]\n\n"
            else:
                formatted_context += f"[Context: {element.content}]\n\n"
        
        # Add the current prompt
        formatted_context += f"User: {prompt}\n\nAssistant:"
        
        return formatted_context
    
    def _format_structured_strategy(
        self,
        prompt: str,
        elements_by_source: dict[str, list[ContextElement]],
        system_instructions: Optional[str]
    ) -> dict[str, Any]:
        """
        Format context as a structured object (e.g., for ChatML or similar formats).
        
        Args:
            prompt: The user's current prompt/query
            elements_by_source: Context elements grouped by source
            system_instructions: System-level instructions for the LLM
            
        Returns:
            Structured object representing the prompt with context
        """
        messages = []

        # Add system message if present
        if system_instructions or "system_instructions" in elements_by_source:
            system_content = system_instructions or ""
            if "system_instructions" in elements_by_source:
                for element in elements_by_source["system_instructions"]:
                    system_content += element.content + "\n\n"

            messages.append({
                "role": "system",
                "content": system_content.strip()
            })

        # Add memory retrieval as system messages
        if "memory_retrieval" in elements_by_source:
            memory_content = "Relevant information from memory:\n\n"
            for element in elements_by_source["memory_retrieval"]:
                memory_type = element.metadata.get("memory_type", "Memory")
                memory_content += f"- {memory_type}: {element.content}\n\n"

            messages.append({
                "role": "system",
                "content": memory_content.strip()
            })

        # Add additional context as system messages
        if "additional_context" in elements_by_source:
            context_content = "Additional context:\n\n"
            for element in elements_by_source["additional_context"]:
                context_key = element.metadata.get("context_key", "Context")
                context_content += f"- {context_key}: {element.content}\n\n"

            messages.append({
                "role": "system",
                "content": context_content.strip()
            })

        # Add conversation history
        if "conversation_history" in elements_by_source:
            # Sort by turn index if available
            conversation_elements = sorted(
                elements_by_source["conversation_history"],
                key=lambda x: x.metadata.get("turn_index", 0) if x.metadata else 0
            )

            for element in conversation_elements:
                content = element.content

                # Parse the content to extract user and assistant messages
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
                    user_content = content.replace("User: ", "", 1).strip()
                    messages.append({
                        "role": "user",
                        "content": user_content
                    })
                elif content.startswith("Assistant: "):
                    assistant_content = content.replace("Assistant: ", "", 1).strip()
                    messages.append({
                        "role": "assistant",
                        "content": assistant_content
                    })

        # Add the current prompt
        messages.append({
            "role": "user",
            "content": prompt
        })

        return {"messages": messages}
    
    def _estimate_structured_token_count(self, structured_prompt: dict[str, Any]) -> int:
        """
        Estimate the token count for a structured prompt.
        
        Args:
            structured_prompt: The structured prompt object
            
        Returns:
            Estimated token count
        """
        # This is a simplified estimation - in production, you would use
        # the actual tokenizer for the model you're using
        total_tokens = 0
        
        if "messages" in structured_prompt:
            for message in structured_prompt["messages"]:
                # Add tokens for the message content
                if "content" in message and message["content"]:
                    total_tokens += self.token_counter(message["content"])
                
                # Add tokens for message structure (role, etc.)
                # This is a rough estimate - actual tokenization depends on the model
                total_tokens += 4  # Approximate overhead per message
        
        return total_tokens


class ContextInjector:
    """
    Lightweight façade around :class:`ContextInjectionManager` for callers.

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
        """
        Create a context injector with an optional explicit configuration.

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
            # Use default configuration
            config = get_default_context_injection_config()

        self.manager = ContextInjectionManager(config)
    def inject(
        self,
        prompt: str,
        conversation_history: list[dict[str, str]] | None = None,
        memory_results: list[MemoryRetrievalResult] | None = None,
        system_instructions: str | None = None,
        additional_context: dict[str, Any] | None = None
    ) -> Union[str, dict[str, Any]]:
        """
        Enrich a prompt with context using the encapsulated manager.

        Summary:
            Provides a single-call wrapper that forwards payloads to the manager
            while preserving the public integration contract.
        Parameters:
            prompt (str): The original user prompt to enrich.
            conversation_history (list[dict[str, str]] | None): Prior turns
                represented as ``{"user": ..., "assistant": ...}``.
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
            additional_context=additional_context
        )


def inject_context(
    prompt: str,
    conversation_history: list[dict[str, str]] | None = None,
    memory_results: list[MemoryRetrievalResult] | None = None,
    system_instructions: str | None = None,
    additional_context: dict[str, Any] | None = None,
    config: ContextInjectionConfig | None = None
) -> Union[str, dict[str, Any]]:
    """
    Convenience wrapper to enrich a prompt with contextual information.

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
        additional_context=additional_context
    )