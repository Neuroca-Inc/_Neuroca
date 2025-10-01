"""Exception module for handler execution failures.

The original handler module defined :class:`EventHandlerExecutionError` inline
next to the `EventBus` implementation. The refactor extracts it into a dedicated
module, preventing circular dependencies while keeping backwards compatibility
with existing imports intact.
"""

from .event_handler_error import EventHandlerError


class EventHandlerExecutionError(EventHandlerError):
    """Raised when a handler fails while processing an event.

    The exception wraps the original error triggered by the handler so that the
    event bus can capture contextual information and continue dispatching to the
    remaining handlers.
    """


__all__ = ["EventHandlerExecutionError"]
