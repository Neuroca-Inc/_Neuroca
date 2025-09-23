"""Decorator utilities for working with function-based handlers."""

from __future__ import annotations

import functools
from typing import Any, Callable, TypeVar, Union, cast

from .event import Event
from .event_bus_error import EventBusError
from .event_priority import EventPriority
from .function_event_handler import FunctionEventHandler
from .instances import event_bus

F = TypeVar("F", bound=Callable[..., Any])


def register_handler(
    event_types: Union[type[Event], list[type[Event]]],
    priority: EventPriority = EventPriority.NORMAL,
) -> Callable[[F], F]:
    """Register a function as an event handler via a decorator.

    Args:
        event_types: Event type or list of event types the function handles.
        priority: Priority applied when dispatching the handler.

    Returns:
        A decorator that registers the function with the global event bus.
    """

    def decorator(func: F) -> F:
        handler = FunctionEventHandler(func, event_types, priority)
        event_bus.register_handler(handler)

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return func(*args, **kwargs)

        setattr(wrapper, "_event_handler", handler)
        return cast(F, wrapper)

    return decorator


def unregister_handler(func: Callable[..., Any]) -> None:
    """Unregister a previously registered function handler.

    Args:
        func: Decorated function returned by :func:`register_handler`.

    Raises:
        EventBusError: Raised when the function was not registered via the
            decorator utility.
    """

    handler = getattr(func, "_event_handler", None)
    if handler is None:
        raise EventBusError(f"Function {func.__name__} is not registered as an event handler")

    event_bus.unregister_handler(handler)
    delattr(func, "_event_handler")


__all__ = ["register_handler", "unregister_handler"]
