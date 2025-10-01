"""Exception module for handler registration failures.

The historical module raised :class:`EventHandlerRegistrationError` when a
consumer attempted to register an invalid handler. The refactor retains the
behaviour while isolating the class so that the one-class-per-file standard is
met without altering imports.
"""

from .event_handler_error import EventHandlerError


class EventHandlerRegistrationError(EventHandlerError):
    """Raised when a handler cannot be registered with the bus.

    The exception typically surfaces when the supplied handler is not an
    instance of :class:`~neuroca.core.events.handlers.event_handler.EventHandler`
    or when the handler advertises event types that do not derive from the
    supported event base classes.
    """


__all__ = ["EventHandlerRegistrationError"]
