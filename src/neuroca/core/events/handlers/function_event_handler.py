"""Function-based implementation of the event handler contract."""

from __future__ import annotations

import inspect
import logging
from typing import Any, Awaitable, Callable, Optional, Union

from .event import Event
from .event_context import EventContext
from .event_handler import EventHandler
from .event_handler_execution_error import EventHandlerExecutionError
from .event_priority import EventPriority

logger = logging.getLogger(__name__)


class FunctionEventHandler(EventHandler):
    """Wrap a callable in the :class:`EventHandler` interface."""

    def __init__(
        self,
        func: Callable[[Event, EventContext], Union[Any, Awaitable[Any]]],
        event_types: Union[type[Event], list[type[Event]]],
        priority: EventPriority = EventPriority.NORMAL,
        name: Optional[str] = None,
    ) -> None:
        """Initialise the handler wrapper.

        Args:
            func: Callable executed when the handler processes an event.
            event_types: Event types supported by the callable.
            priority: Scheduling priority used by the event bus.
            name: Optional label to override the derived handler name.
        """

        super().__init__(event_types, priority, name or func.__name__)
        self.func = func

    async def handle(self, event: Event, context: EventContext) -> Any:
        """Invoke the wrapped callable and propagate the result.

        Args:
            event: Event payload forwarded by the bus.
            context: Execution context shared by the dispatch chain.

        Returns:
            Whatever value the wrapped callable returns.

        Raises:
            EventHandlerExecutionError: Raised when the callable fails.
        """

        try:
            if inspect.iscoroutinefunction(self.func):
                return await self.func(event, context)
            return self.func(event, context)
        except Exception as error:  # pragma: no cover - defensive logging branch
            logger.error("Error executing handler %s: %s", self.id, error, exc_info=True)
            raise EventHandlerExecutionError(str(error)) from error


__all__ = ["FunctionEventHandler"]
