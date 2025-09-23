"""Event bus implementation coordinating handler execution."""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

from .event import Event
from .event_context import EventContext
from .event_handler import EventHandler
from .event_handler_registration_error import EventHandlerRegistrationError
from .event_bus_error import EventBusError

try:  # Import guarded to avoid circular imports in constrained runtimes.
    from neuroca.core.events.base import BaseEvent as _BaseEvent
except Exception:  # pragma: no cover - defensive import guard
    _BaseEvent = None  # type: ignore

logger = logging.getLogger(__name__)

# Shared thread-local store used to nest event contexts.
EVENT_CONTEXT_STATE = threading.local()


class EventBus:
    """Publish-subscribe coordinator for legacy event handlers."""

    def __init__(self) -> None:
        self._handlers: dict[type[Event], list[EventHandler]] = {}
        self._all_handlers: set[EventHandler] = set()
        self._lock = threading.RLock()

    def register_handler(self, handler: EventHandler) -> None:
        """Register a handler with the bus.

        Args:
            handler: Handler instance implementing the event contract.

        Raises:
            EventHandlerRegistrationError: Raised when the handler is invalid.
        """

        if not isinstance(handler, EventHandler):
            raise EventHandlerRegistrationError(
                f"Handler must be an instance of EventHandler, got {type(handler)}"
            )

        with self._lock:
            self._all_handlers.add(handler)

            for event_type in handler.event_types:
                if not self._is_supported_event_type(event_type):
                    raise EventHandlerRegistrationError(
                        f"Event type must derive from Event/BaseEvent, got {event_type}"
                    )

                self._handlers.setdefault(event_type, []).append(handler)
                self._handlers[event_type].sort(key=lambda candidate: candidate.priority)

        logger.debug(
            "Registered handler %s for event types: %s",
            handler.id,
            [event_type.__name__ for event_type in handler.event_types],
        )

    def unregister_handler(self, handler: EventHandler) -> None:
        """Remove a handler from the bus.

        Args:
            handler: Handler instance previously registered with the bus.
        """

        with self._lock:
            self._all_handlers.discard(handler)

            for event_type in list(self._handlers.keys()):
                if handler in self._handlers[event_type]:
                    self._handlers[event_type].remove(handler)
                    if not self._handlers[event_type]:
                        del self._handlers[event_type]

        logger.debug("Unregistered handler %s", handler.id)

    def get_handlers_for_event(self, event: Event) -> list[EventHandler]:
        """Return handlers that can process the provided event.

        Args:
            event: Event instance for which compatible handlers are requested.

        Returns:
            Handlers sorted by priority that can process the event.
        """

        with self._lock:
            handlers: list[EventHandler] = []
            event_type = type(event)

            if event_type in self._handlers:
                handlers.extend(self._handlers[event_type])

            for registered_type, type_handlers in self._handlers.items():
                if registered_type != event_type and issubclass(event_type, registered_type):
                    handlers.extend(handler for handler in type_handlers if handler not in handlers)

            return sorted(handlers, key=lambda candidate: candidate.priority)

    async def publish(self, event: Any) -> EventContext:
        """Publish an event to all registered handlers.

        Args:
            event: Event (or compatible base event) that should be dispatched.

        Returns:
            Event context populated with execution statistics and results.

        Raises:
            EventBusError: Raised when dispatch fails catastrophically.
        """

        if not self._is_supported_event(event):
            raise EventBusError(f"Can only publish Event/BaseEvent objects, got {type(event)}")

        parent_context_id = getattr(EVENT_CONTEXT_STATE, "current_context_id", None)
        context = EventContext(event, parent_context_id)
        EVENT_CONTEXT_STATE.current_context_id = context.context_id

        try:
            return await self._dispatch_handlers(event, context)
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

    async def _dispatch_handlers(self, event: Event, context: EventContext) -> EventContext:
        """Execute registered handlers for the event.

        Args:
            event: Event being processed.
            context: Context shared across handler invocations.

        Returns:
            The populated event context.
        """

        logger.debug("Publishing event %s of type %s", event.id, type(event).__name__)

        handlers = self.get_handlers_for_event(event)
        if not handlers:
            logger.debug("No handlers registered for event type %s", type(event).__name__)
            return context

        for handler in handlers:
            if not handler.enabled:
                continue

            if context.propagation_stopped:
                logger.debug("Event propagation stopped before handler %s", handler.id)
                break

            try:
                start_time = time.time()
                result = await handler.handle(event, context)
                execution_time = time.time() - start_time

                context.add_result(handler.id, result)
                context.record_execution_time(handler.id, execution_time)

                logger.debug(
                    "Handler %s processed event %s in %.4fs",
                    handler.id,
                    event.id,
                    execution_time,
                )
            except Exception as error:
                error_message = f"Error in handler {handler.id} for event {event.id}: {error}"
                logger.error(error_message, exc_info=True)
                context.add_error(handler.id, error)

        return context

    @staticmethod
    def _is_supported_event(event: Any) -> bool:
        """Return whether the event instance can be dispatched."""

        return isinstance(event, Event) or (
            _BaseEvent is not None and isinstance(event, _BaseEvent)
        )

    @staticmethod
    def _is_supported_event_type(event_type: type) -> bool:
        """Return whether the supplied type can be registered with the bus."""

        try:
            is_event = issubclass(event_type, Event)
        except TypeError:
            is_event = False

        is_base_event = False
        if _BaseEvent is not None:
            try:
                is_base_event = issubclass(event_type, _BaseEvent)  # type: ignore[arg-type]
            except TypeError:
                is_base_event = False

        return is_event or is_base_event


BASE_EVENT_TYPE = _BaseEvent

__all__ = ["BASE_EVENT_TYPE", "EVENT_CONTEXT_STATE", "EventBus"]
