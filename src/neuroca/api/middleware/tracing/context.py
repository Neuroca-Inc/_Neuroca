"""Context helpers for tracing middleware state."""

from contextvars import ContextVar

__all__ = [
    "current_request_id",
    "current_trace_id",
    "get_request_id",
    "get_trace_id",
]

current_request_id: ContextVar[str] = ContextVar("current_request_id", default="")
"""Context variable storing the active request identifier."""

current_trace_id: ContextVar[str] = ContextVar("current_trace_id", default="")
"""Context variable storing the active trace identifier."""


def get_request_id() -> str:
    """Return the request identifier stored in the tracing context.

    Returns:
        str: The identifier associated with the active HTTP request. When no
            identifier has been recorded the function returns an empty string.
    """

    return current_request_id.get()


def get_trace_id() -> str:
    """Return the trace identifier stored in the tracing context.

    Returns:
        str: The OpenTelemetry trace identifier for the current request or an
            empty string if tracing has not been initialised.
    """

    return current_trace_id.get()
