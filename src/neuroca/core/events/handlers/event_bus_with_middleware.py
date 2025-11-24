"""Event bus variant that supports middleware execution."""

from __future__ import annotations

import logging
from typing import Any

from .event import Event
from .event_context import EventContext
from .event_bus import EVENT_CONTEXT_STATE, EventBus
from .event_bus_error import EventBusError
from .event_middleware import EventMiddleware

logger = logging.getLogger(__name__)


class EventBusWithMiddleware(EventBus):
    """Extends :class:`EventBus` with middleware support."""

    def __init__(self) -> None:
        super().__init__()
        self._middleware: list[EventMiddleware] = []

    def add_middleware(self, middleware: EventMiddleware) -> None:
        """Add middleware to the bus.

        Args:
            middleware: Middleware component to append to the execution chain.

        Raises:
            EventBusError: Raised when the middleware does not implement the
                expected interface.
        """

        if not isinstance(middleware, EventMiddleware):
            raise EventBusError(
                f"Middleware must be an instance of EventMiddleware, got {type(middleware)}"
            )
        self._middleware.append(middleware)
        logger.debug("Added middleware: %s", middleware.__class__.__name__)

    def remove_middleware(self, middleware: EventMiddleware) -> None:
        """Remove middleware from the bus if present.

        Args:
            middleware: Middleware component to remove.
        """

        if middleware in self._middleware:
            self._middleware.remove(middleware)
            logger.debug("Removed middleware: %s", middleware.__class__.__name__)

    async def publish(self, event: Any) -> EventContext:
        """Publish an event through the middleware pipeline before handlers.

        Args:
            event: Event (or compatible base event) to dispatch.

        Returns:
            Populated event context containing middleware and handler results.

        Raises:
            EventBusError: Raised when dispatch fails catastrophically.
        """

        if not self._middleware:
            return await super().publish(event)

        if not self._is_supported_event(event):
            raise EventBusError(f"Can only publish Event/BaseEvent objects, got {type(event)}")

        parent_context_id = getattr(EVENT_CONTEXT_STATE, "current_context_id", None)
        context = EventContext(event, parent_context_id)
        EVENT_CONTEXT_STATE.current_context_id = context.context_id

        try:
            return await self._process_middleware(event, context, 0)
        except Exception as error:
            error_message = f"Error publishing event {event.id}: {error}"
            logger.error(error_message, exc_info=True)
            raise EventBusError(error_message) from error
        finally:
            if parent_context_id:
                EVENT_CONTEXT_STATE.current_context_id = parent_context_id
            else:
                if hasattr(EVENT_CONTEXT_STATE, "current_context_id"):
                    delattr(EVENT_CONTEXT_STATE, "current_context_id")

    async def _process_middleware(
        self, event: Event, context: EventContext, index: int
    ) -> EventContext:
        """Process the event through middleware in order.

        Args:
            event: Event being dispatched.
            context: Context shared across middleware and handlers.
            index: Current middleware index within the chain.

        Returns:
            Event context returned by the downstream middleware or handlers.
        """

        if index >= len(self._middleware):
            return await self._dispatch_handlers(event, context)

        middleware = self._middleware[index]

        async def next_middleware() -> EventContext:
            return await self._process_middleware(event, context, index + 1)

        return await middleware.process(event, context, next_middleware)


__all__ = ["EventBusWithMiddleware"]
