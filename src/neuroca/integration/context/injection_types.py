"""Context injection shared enumerations and dataclasses.

Purpose:
    Provide immutable typing primitives that describe context injection
    priorities, formatting, and element metadata so other modules can compose
    behaviour without re-declaring structural details.
External Dependencies:
    Standard library only; no CLI or HTTP calls are performed here.
Fallback Semantics:
    No fallback logic is implemented. Callers are expected to supply valid
    enumeration members and respect the documented invariants.
Timeout Strategy:
    Not applicable. All operations are synchronous and CPU-bound.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class ContextPriority(Enum):
    """Define the relative importance of context elements during selection.

    Summary:
        Enumerates priority buckets that govern which context elements survive
        when token budgets require trimming.
    Side Effects:
        None. Enumeration values are immutable constants.
    Timeout/Retry Notes:
        Not applicable.
    """

    CRITICAL = 0
    HIGH = 1
    MEDIUM = 2
    LOW = 3
    BACKGROUND = 4


class ContextFormat(Enum):
    """Enumerate supported downstream payload formats for LLM providers.

    Summary:
        Informs formatting helpers how to serialise the enriched prompt for a
        given provider family (OpenAI, Anthropic, Google, or custom flows).
    Side Effects:
        None. Enumeration lookup is side-effect free.
    Timeout/Retry Notes:
        Not applicable.
    """

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    CUSTOM = "custom"


class ContextInjectionStrategy(Enum):
    """Describe how selected context should be merged with the base prompt.

    Summary:
        Provides a stable vocabulary for injection strategies (prepend, append,
        interleave, structured) consumed by formatting helpers.
    Side Effects:
        None. Enumeration values are constant metadata.
    Timeout/Retry Notes:
        Not applicable.
    """

    PREPEND = "prepend"
    APPEND = "append"
    INTERLEAVE = "interleave"
    STRUCTURED = "structured"


@dataclass
class ContextElement:
    """Container for a single context fragment scheduled for injection.

    Summary:
        Stores the textual payload, provenance metadata, and priority that guide
        selection and formatting routines.
    Parameters:
        content (str): Human-readable text representing the context fragment.
        source (str): Logical origin such as ``"working_memory"`` or
            ``"conversation_history"``.
        priority (ContextPriority): Priority bucket associated with the element.
        token_count (int): Estimated token footprint used during budget checks.
        metadata (dict[str, Any] | None): Optional auxiliary metadata for the
            element (e.g., memory type, turn index).
    Returns:
        ContextElement: Dataclass instance ready for downstream processing.
    Raises:
        None.
    Side Effects:
        Instances are pure data holders; no side effects occur during
        instantiation aside from attribute assignment.
    Timeout/Retry Notes:
        Not applicable.
    """

    content: str
    source: str
    priority: ContextPriority
    token_count: int
    metadata: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        """Normalise the metadata container after initialisation.

        Summary:
            Ensures downstream consumers always interact with a dictionary even
            when callers omit metadata during construction.
        Parameters:
            None
        Returns:
            None
        Raises:
            None
        Side Effects:
            Mutates ``self.metadata`` to an empty dictionary when ``None`` is
            supplied.
        Timeout/Retry Notes:
            Not applicable.
        """

        if self.metadata is None:
            self.metadata = {}
