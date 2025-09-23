"""Middleware that logs events flowing through the bus."""

from __future__ import annotations

import logging
from typing import Awaitable, Callable

from .event import Event
from .event_context import EventContext
from .event_middleware import EventMiddleware

logger = logging.getLogger(__name__)


class LoggingMiddleware(EventMiddleware):
    """Middleware that records basic event telemetry to the logger."""

    async def process(
        self,
        event: Event,
        context: EventContext,
        next_middleware: Callable[[], Awaitable[EventContext]],
    ) -> EventContext:
        """Log the inbound event, delegate, and log the result.

        Args:
            event: Event currently being processed.
            context: Event context passed down the middleware chain.
            next_middleware: Callable that continues execution with the rest of
                the middleware stack.

        Returns:
            The event context returned by the downstream middleware or handlers.
        """

        logger.info("Event received: %s (ID: %s)", type(event).__name__, event.id)
        try:
            result_context = await next_middleware()
            if result_context.has_errors:
                logger.warning(
                    "Event %s processed with %d errors in %.4fs",
                    event.id,
                    len(result_context.errors),
                    result_context.total_execution_time,
                )
            else:
                logger.info(
                    "Event %s processed successfully in %.4fs",
                    event.id,
                    result_context.total_execution_time,
                )
            return result_context
        except Exception as error:  # pragma: no cover - defensive logging branch
            logger.error("Error processing event %s: %s", event.id, error, exc_info=True)
            raise


__all__ = ["LoggingMiddleware"]
