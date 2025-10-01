"""Base exception hierarchy for the handler subsystem.

Historically the event handling module exposed a single file containing all
exception types. The refactor keeps the surface area intact while moving the
base class into its own module so that derived exceptions can import it without
risking circular dependencies.
"""


class EventHandlerError(Exception):
    """Base exception for failures within the event handler infrastructure.

    The exception acts as a marker so orchestration code can gracefully catch
    and report handler-specific problems without masking unrelated runtime
    errors.
    """


__all__ = ["EventHandlerError"]
