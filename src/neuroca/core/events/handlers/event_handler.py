"""Abstract base class for event handlers."""

from __future__ import annotations

import abc
import uuid
from typing import Any, Iterable, Optional, Union

from .event import Event
from .event_context import EventContext
from .event_priority import EventPriority


class EventHandler(abc.ABC):
    """Base class describing the legacy handler contract.

    Args:
        event_types: Iterable of event classes that the handler supports.
        priority: Priority applied when scheduling handler execution.
        name: Optional friendly identifier for logging and debugging.
    """

    def __init__(
        self,
        event_types: Union[type[Event], Iterable[type[Event]]],
        priority: EventPriority = EventPriority.NORMAL,
        name: Optional[str] = None,
    ) -> None:
        if isinstance(event_types, type):
            self.event_types = [event_types]
        else:
            self.event_types = list(event_types)
        self.priority = priority
        self.name = name or self.__class__.__name__
        self.id = f"{self.name}_{str(uuid.uuid4())[:8]}"
        self.enabled = True

    @abc.abstractmethod
    async def handle(self, event: Event, context: EventContext) -> Any:
        """Process an event dispatched by the bus.

        Args:
            event: The event payload the handler should process.
            context: Shared execution context that spans the dispatch chain.

        Returns:
            Optional result value that the bus records for later inspection.

        Raises:
            EventHandlerExecutionError: Implementations may raise the error to
                signal failure; the bus will log it and continue dispatch.
        """

    def can_handle(self, event: Event) -> bool:
        """Return whether the handler can process the provided event."""

        return any(isinstance(event, event_type) for event_type in self.event_types)

    def enable(self) -> None:
        """Enable the handler for subsequent dispatches."""

        self.enabled = True

    def disable(self) -> None:
        """Disable the handler to prevent dispatch."""

        self.enabled = False


__all__ = ["EventHandler"]
