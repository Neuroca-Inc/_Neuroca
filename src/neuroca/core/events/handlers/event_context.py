"""Context container shared across handler invocations."""

from __future__ import annotations

import time
import uuid
from typing import Any, Optional

from .event import Event


class EventContext:
    """Runtime context propagated to each handler during dispatch.

    Attributes:
        context_id: Unique identifier for the context for tracing purposes.
        event: The event being processed.
        parent_context_id: Identifier of the parent context if the event was
            published during another handler's execution.
        start_time: Timestamp recorded when the context was created.
        propagation_stopped: Flag indicating whether further dispatch should be
            halted.
        results: Mapping between handler IDs and their returned results.
        errors: Sequence of tuples pairing handler IDs with raised exceptions.
        handler_execution_times: Execution duration recorded per handler.
    """

    def __init__(self, event: Event, parent_context_id: Optional[str] = None) -> None:
        self.context_id = str(uuid.uuid4())
        self.event = event
        self.parent_context_id = parent_context_id
        self.start_time = time.time()
        self.propagation_stopped = False
        self.results: dict[str, Any] = {}
        self.errors: list[tuple[str, Exception]] = []
        self.handler_execution_times: dict[str, float] = {}

    def stop_propagation(self) -> None:
        """Stop dispatching the event to subsequent handlers."""

        self.propagation_stopped = True

    def add_result(self, handler_id: str, result: Any) -> None:
        """Record a handler's result for later inspection.

        Args:
            handler_id: Identifier of the handler that produced the result.
            result: The value returned by the handler.
        """

        self.results[handler_id] = result

    def add_error(self, handler_id: str, error: Exception) -> None:
        """Record an error raised by a handler.

        Args:
            handler_id: Identifier of the handler that raised the error.
            error: The exception instance caught during execution.
        """

        self.errors.append((handler_id, error))

    def record_execution_time(self, handler_id: str, execution_time: float) -> None:
        """Record the execution time observed for a handler.

        Args:
            handler_id: Identifier of the handler that executed.
            execution_time: Duration in seconds that the handler took to run.
        """

        self.handler_execution_times[handler_id] = execution_time

    @property
    def total_execution_time(self) -> float:
        """Return the total time spent processing the event so far."""

        return time.time() - self.start_time

    @property
    def has_errors(self) -> bool:
        """Return whether any handler raised an exception."""

        return bool(self.errors)


__all__ = ["EventContext"]
