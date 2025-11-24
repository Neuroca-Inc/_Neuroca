"""Transactional helpers for cross-tier consolidation."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable, Dict, Optional


logger = logging.getLogger(__name__)


class ConsolidationSkip(Exception):
    """Signal that the current consolidation attempt should be skipped."""


RollbackCallback = Callable[[Any], Awaitable[None]]
TransactionCallable = Callable[["ConsolidationTransaction"], Awaitable[Any]]


class ConsolidationTransaction:
    """Execute consolidation steps with rollback support."""

    def __init__(self, name: str, *, log: Optional[logging.Logger] = None) -> None:
        self._name = name
        self._log = log or logger
        self._rollback_stack: list[Callable[[], Awaitable[None]]] = []

    async def stage(
        self,
        action: Callable[[], Awaitable[Any]],
        *,
        rollback: Optional[RollbackCallback] = None,
        description: str | None = None,
    ) -> Any:
        """Run ``action`` and register an optional rollback handler."""

        step = description or getattr(action, "__name__", "step")

        try:
            result = await action()
        except Exception as exc:  # noqa: BLE001
            self._log.exception(
                "Consolidation transaction %s failed during step %s due to %s",
                self._name,
                step,
                exc,
            )
            raise

        if rollback is not None:
            async def _rollback() -> None:
                try:
                    await rollback(result)
                except Exception:  # noqa: BLE001
                    self._log.exception(
                        "Rollback for step %s failed in consolidation transaction %s",
                        step,
                        self._name,
                    )

            self._rollback_stack.append(_rollback)

        return result

    async def execute(self, runner: TransactionCallable) -> Any:
        """Execute the transaction runner with automatic rollback handling."""

        try:
            return await runner(self)
        except ConsolidationSkip:
            await self.rollback()
            raise
        except Exception:
            await self.rollback()
            raise

    async def rollback(self) -> None:
        """Invoke registered rollback callbacks in reverse order."""

        while self._rollback_stack:
            callback = self._rollback_stack.pop()
            try:
                await callback()
            except Exception:  # noqa: BLE001
                self._log.exception(
                    "Rollback callback failed in consolidation transaction %s",
                    self._name,
                )


class TransactionalConsolidationPipeline:
    """Coordinate consolidation transactions with idempotency guarantees."""

    def __init__(self, *, log: Optional[logging.Logger] = None) -> None:
        self._log = log or logger
        self._locks: Dict[str, asyncio.Lock] = {}
        self._completed: Dict[str, Any] = {}

    async def run(self, key: str, runner: TransactionCallable) -> Any:
        """Execute ``runner`` for ``key`` if it has not completed previously."""

        lock = self._locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[key] = lock

        async with lock:
            if key in self._completed:
                return self._completed[key]

            transaction = ConsolidationTransaction(key, log=self._log)

            try:
                result = await transaction.execute(runner)
            except ConsolidationSkip:
                return None
            except Exception:
                raise

            self._completed[key] = result
            return result


__all__ = [
    "ConsolidationSkip",
    "ConsolidationTransaction",
    "TransactionalConsolidationPipeline",
]
