"""Global handler infrastructure instances used throughout the codebase."""

from __future__ import annotations

from .event_bus import EventBus
from .event_bus_with_middleware import EventBusWithMiddleware
from .logging_middleware import LoggingMiddleware

# Legacy compatibility: expose the global bus instances expected by callers.
event_bus = EventBus()
event_bus_with_middleware = EventBusWithMiddleware()
event_bus_with_middleware.add_middleware(LoggingMiddleware())

__all__ = ["event_bus", "event_bus_with_middleware"]
