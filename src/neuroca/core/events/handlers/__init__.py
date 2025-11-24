"""Event handler infrastructure with single-class modules."""

from .decorators import register_handler, unregister_handler
from .event import Event
from .event_bus import BASE_EVENT_TYPE, EVENT_CONTEXT_STATE, EventBus
from .event_bus_error import EventBusError
from .event_bus_with_middleware import EventBusWithMiddleware
from .event_context import EventContext
from .event_handler import EventHandler
from .event_handler_error import EventHandlerError
from .event_handler_execution_error import EventHandlerExecutionError
from .event_handler_registration_error import EventHandlerRegistrationError
from .event_middleware import EventMiddleware
from .event_priority import EventPriority
from .function_event_handler import FunctionEventHandler
from .instances import event_bus, event_bus_with_middleware
from .logging_middleware import LoggingMiddleware

__all__ = [
    "BASE_EVENT_TYPE",
    "EVENT_CONTEXT_STATE",
    "Event",
    "EventBus",
    "EventBusError",
    "EventBusWithMiddleware",
    "EventContext",
    "EventHandler",
    "EventHandlerError",
    "EventHandlerExecutionError",
    "EventHandlerRegistrationError",
    "EventMiddleware",
    "EventPriority",
    "FunctionEventHandler",
    "LoggingMiddleware",
    "event_bus",
    "event_bus_with_middleware",
    "register_handler",
    "unregister_handler",
]
