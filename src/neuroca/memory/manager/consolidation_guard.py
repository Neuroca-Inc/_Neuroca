"""Deduplication helpers for consolidation workflows."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class ConsolidationGuardDecision:
    """Represents the outcome of a consolidation reservation request."""

    proceed: bool
    """Whether the caller should execute the consolidation logic."""

    result: Any | None
    """Cached result from a prior consolidation attempt if available."""

    reservation: "ConsolidationReservation | None"
    """Reservation context to execute the consolidation when ``proceed`` is ``True``."""


class ConsolidationReservation:
    """Context manager that finalizes in-flight consolidation tracking."""

    def __init__(
        self,
        guard: "ConsolidationInFlightGuard",
        key: str,
    ) -> None:
        self._guard = guard
        self._key = key
        self._has_result = False
        self._result: Any | None = None

    def commit(self, result: Any | None) -> None:
        """Mark the consolidation as completed successfully with ``result``."""

        self._has_result = True
        self._result = result

    async def __aenter__(self) -> "ConsolidationReservation":
        return self

    async def __aexit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc: Optional[BaseException],
        _traceback: Any,
    ) -> None:
        error: BaseException | None = exc if exc_type is not None else None
        result: Any | None = self._result if self._has_result and error is None else None
        await self._guard._finalize(self._key, result=result, error=error)


class ConsolidationInFlightGuard:
    """Coordinate consolidation requests across concurrent callers."""

    def __init__(self, *, dedupe_window_seconds: float = 30.0) -> None:
        self._dedupe_window = max(0.0, dedupe_window_seconds)
        self._state_lock = asyncio.Lock()
        self._inflight: Dict[str, asyncio.Future[Any]] = {}
        self._completed: Dict[str, tuple[float, Any]] = {}

    async def reserve(self, key: str) -> ConsolidationGuardDecision:
        """Reserve consolidation execution for ``key`` or return cached results."""

        loop = asyncio.get_running_loop()

        while True:
            async with self._state_lock:
                now = time.monotonic()
                self._purge_expired(now)

                cached = self._completed.get(key)
                if cached is not None:
                    expires_at, result = cached
                    if now < expires_at:
                        return ConsolidationGuardDecision(
                            proceed=False,
                            result=result,
                            reservation=None,
                        )
                    self._completed.pop(key, None)

                future = self._inflight.get(key)
                if future is None:
                    future = loop.create_future()
                    self._inflight[key] = future
                    reservation = ConsolidationReservation(self, key)
                    return ConsolidationGuardDecision(
                        proceed=True,
                        result=None,
                        reservation=reservation,
                    )

                waiter = future

            try:
                result = await waiter
            except Exception:
                # Allow a new attempt if the prior run failed.
                continue

            return ConsolidationGuardDecision(
                proceed=False,
                result=result,
                reservation=None,
            )

    async def wait_for_all(self, *, timeout: float | None = None) -> None:
        """Wait for all currently in-flight consolidations to complete."""

        async with self._state_lock:
            futures = [asyncio.shield(task) for task in self._inflight.values()]

        if not futures:
            return

        waiter = asyncio.gather(*futures, return_exceptions=True)

        if timeout is None or timeout <= 0:
            await waiter
            return

        await asyncio.wait_for(waiter, timeout=timeout)

    async def _finalize(
        self,
        key: str,
        *,
        result: Any | None,
        error: BaseException | None,
    ) -> None:
        """Mark the consolidation for ``key`` as finished and unblock waiters."""

        async with self._state_lock:
            active = self._inflight.pop(key, None)
            if active is not None and not active.done():
                if error is not None:
                    active.set_exception(error)
                else:
                    active.set_result(result)

            if error is None and result is not None and self._dedupe_window > 0.0:
                self._completed[key] = (time.monotonic() + self._dedupe_window, result)
            else:
                self._completed.pop(key, None)

    def _purge_expired(self, now: float) -> None:
        expired = [key for key, (expires_at, _) in self._completed.items() if expires_at <= now]
        for key in expired:
            self._completed.pop(key, None)


__all__ = [
    "ConsolidationGuardDecision",
    "ConsolidationInFlightGuard",
    "ConsolidationReservation",
]
