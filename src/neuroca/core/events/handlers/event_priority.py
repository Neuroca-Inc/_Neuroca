"""Priority definitions for event handlers.

This module exposes :class:`EventPriority`, the enumeration that the event
handling infrastructure uses to order handler execution. The enum lives in its
own module to satisfy the one-class-per-file guideline while keeping the
handler package's public API stable.
"""

from enum import IntEnum


class EventPriority(IntEnum):
    """Execution priority levels for event handlers.

    Attributes:
        CRITICAL: Immediate processing; handler runs before all others.
        HIGH: Elevated priority for latency-sensitive handlers.
        NORMAL: Default priority applied when none is specified.
        LOW: Background work that should yield to more urgent handlers.
        BACKGROUND: Lowest priority for maintenance tasks.
    """

    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3
    BACKGROUND = 4


__all__ = ["EventPriority"]
