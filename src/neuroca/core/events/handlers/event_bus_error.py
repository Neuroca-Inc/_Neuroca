"""Exception module for event bus failures.

The :class:`EventBusError` type signals problems with publishing or middleware
execution. Splitting it into a dedicated module avoids circular imports and
satisfies the one-class-per-file standard.
"""

from .event_handler_error import EventHandlerError


class EventBusError(EventHandlerError):
    """Raised when the event bus encounters an unrecoverable error.

    The exception wraps low-level failures triggered during event dispatch so
    higher layers can record a consistent error type for observability.
    """


__all__ = ["EventBusError"]
