"""Base class for event middleware components."""

from __future__ import annotations

import abc
from typing import Callable

from .event import Event
from .event_context import EventContext


class EventMiddleware(abc.ABC):
    """Contract for middleware executed before handlers."""

    @abc.abstractmethod
    async def process(
        self,
        event: Event,
        context: EventContext,
        next_middleware: Callable[[], object],
    ) -> EventContext:
        """Process an event and delegate to the next middleware.

        Args:
            event: Event being processed.
            context: Context shared throughout the dispatch chain.
            next_middleware: Callable that continues evaluation through the
                middleware stack.

        Returns:
            Updated event context after the middleware completes.
        """


__all__ = ["EventMiddleware"]
