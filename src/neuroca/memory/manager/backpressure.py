"""Back-pressure coordination for tiered memory ingestion."""

from __future__ import annotations

import asyncio
import logging
from collections import deque
from dataclasses import dataclass
from typing import Any, Deque, Dict, Optional

from neuroca.memory.exceptions import MemoryBackpressureError


logger = logging.getLogger(__name__)


def _coerce_positive_int(value: Any) -> int | None:
    """Return ``value`` as a positive integer or ``None`` if invalid."""

    try:
        candidate = int(value)
    except (TypeError, ValueError):
        return None

    return candidate if candidate > 0 else None


def _coerce_timeout(value: Any) -> float | None:
    """Return ``value`` as a positive timeout in seconds or ``None``."""

    try:
        candidate = float(value)
    except (TypeError, ValueError):
        return None

    return candidate if candidate > 0 else None


@dataclass(slots=True)
class TierBackpressureSettings:
    """Configuration describing the ingest back-pressure policy for a tier."""

    name: str
    max_inflight: int | None = None
    max_queue: int | None = 64
    overflow_policy: str = "queue"
    wait_timeout_seconds: float | None = None

    @classmethod
    def from_config(
        cls,
        name: str,
        config: Dict[str, Any] | None,
    ) -> "TierBackpressureSettings":
        """Construct a settings object from raw configuration values."""

        config = dict(config or {})

        max_inflight = _coerce_positive_int(config.get("max_inflight"))
        raw_queue = config.get("max_queue")
        max_queue = _coerce_positive_int(raw_queue)
        if max_queue is None and raw_queue is not None:
            try:
                if int(raw_queue) == 0:
                    max_queue = 0
            except (TypeError, ValueError):
                max_queue = None
        overflow_policy = str(config.get("overflow_policy", "queue")).strip().lower()
        if overflow_policy not in {"queue", "reject"}:
            overflow_policy = "queue"

        wait_timeout = _coerce_timeout(
            config.get("wait_timeout_seconds", config.get("wait_timeout"))
        )

        if overflow_policy == "reject":
            max_queue = 0

        return cls(
            name=name,
            max_inflight=max_inflight,
            max_queue=max_queue,
            overflow_policy=overflow_policy,
            wait_timeout_seconds=wait_timeout,
        )

    @property
    def enabled(self) -> bool:
        """Return ``True`` when the tier enforces back-pressure."""

        return self.max_inflight is not None


class _TierState:
    """Runtime coordination state for a tier."""

    def __init__(
        self,
        settings: TierBackpressureSettings,
        *,
        log: logging.Logger,
    ) -> None:
        self.settings = settings
        self._log = log
        self._lock = asyncio.Lock()
        self._inflight = 0
        self._waiters: Deque[asyncio.Future[None]] = deque()

    def snapshot(self) -> Dict[str, int]:
        """Return a diagnostic snapshot of the tier state."""

        return {
            "inflight": self._inflight,
            "queued": len(self._waiters),
        }

    async def acquire(self) -> "_AcquiredHandle":
        """Acquire an ingest slot honouring the configured policy."""

        if not self.settings.enabled:
            return _AcquiredHandle(self, counted=False)

        waiter: asyncio.Future[None] | None = None
        async with self._lock:
            if self._inflight < (self.settings.max_inflight or 0):
                self._inflight += 1
                return _AcquiredHandle(self, counted=True)

            if self.settings.overflow_policy == "reject":
                raise MemoryBackpressureError(
                    f"{self.settings.name} tier is throttling new writes"
                )

            queue_limit = self.settings.max_queue
            if queue_limit is not None and len(self._waiters) >= queue_limit:
                raise MemoryBackpressureError(
                    f"{self.settings.name} tier back-pressure queue is full"
                )

            waiter = asyncio.get_running_loop().create_future()
            self._waiters.append(waiter)
            self._log.debug(
                "Queued memory ingest for tier %s (inflight=%s, queued=%s)",
                self.settings.name,
                self._inflight,
                len(self._waiters),
            )

        try:
            if self.settings.wait_timeout_seconds:
                await asyncio.wait_for(
                    waiter, timeout=self.settings.wait_timeout_seconds
                )
            else:
                await waiter
        except asyncio.TimeoutError as exc:
            await self._drop_waiter(waiter)
            self._log.warning(
                "Timed out waiting for back-pressure relief in tier %s after %.2fs",
                self.settings.name,
                self.settings.wait_timeout_seconds,
            )
            raise MemoryBackpressureError(
                f"Timed out waiting for {self.settings.name} ingest capacity"
            ) from exc
        except Exception:
            await self._drop_waiter(waiter)
            raise

        return _AcquiredHandle(self, counted=True)

    async def release(self, counted: bool) -> None:
        """Release an ingest slot and wake queued writers if needed."""

        if not counted:
            return

        next_waiter: asyncio.Future[None] | None = None
        async with self._lock:
            if self._inflight > 0:
                self._inflight -= 1

            if self._waiters:
                next_waiter = self._waiters.popleft()
                self._inflight += 1

        if next_waiter and not next_waiter.done():
            next_waiter.set_result(None)

    async def _drop_waiter(self, waiter: asyncio.Future[None]) -> None:
        """Remove ``waiter`` from the queue after cancellation or timeout."""

        async with self._lock:
            try:
                self._waiters.remove(waiter)
            except ValueError:  # pragma: no cover - already handled elsewhere
                return


class _AcquiredHandle:
    """Small helper that ties a tier state to its release semantics."""

    def __init__(self, state: _TierState, *, counted: bool) -> None:
        self._state = state
        self._counted = counted

    async def release(self) -> None:
        await self._state.release(self._counted)


class _BackpressureSlot:
    """Async context manager returned to callers."""

    def __init__(self, controller: "BackpressureController", tier: str) -> None:
        self._controller = controller
        self._tier = tier
        self._handle: _AcquiredHandle | None = None

    async def __aenter__(self) -> None:
        self._handle = await self._controller._acquire(self._tier)
        return None

    async def __aexit__(self, exc_type, exc, tb) -> Optional[bool]:  # noqa: D401
        await self._controller._release(self._tier, self._handle)
        self._handle = None
        return None


class BackpressureController:
    """Coordinate ingest back-pressure across tiers."""

    def __init__(
        self,
        tiers: Dict[str, TierBackpressureSettings] | None = None,
        *,
        log: logging.Logger | None = None,
    ) -> None:
        self._log = log or logger.getChild("controller")
        self._tiers: Dict[str, _TierState] = {}

        for name, settings in (tiers or {}).items():
            tier_log = self._log.getChild(name)
            self._tiers[name] = _TierState(settings, log=tier_log)

    @classmethod
    def from_config(
        cls,
        config: Dict[str, Any] | None,
        *,
        log: logging.Logger | None = None,
    ) -> "BackpressureController":
        """Construct a controller from manager configuration."""

        config = config or {}
        default_section = config.get("default")
        default_config = dict(default_section) if isinstance(default_section, dict) else {}

        tiers: Dict[str, TierBackpressureSettings] = {}
        for tier_name in ("stm", "mtm", "ltm"):
            tier_section = config.get(tier_name)
            tier_config = dict(default_config)
            if isinstance(tier_section, dict):
                tier_config.update(tier_section)
            tiers[tier_name] = TierBackpressureSettings.from_config(tier_name, tier_config)

        return cls(tiers, log=log)

    def slot(self, tier_name: str) -> _BackpressureSlot:
        """Return an async context manager guarding writes to ``tier_name``."""

        return _BackpressureSlot(self, tier_name)

    async def _acquire(self, tier_name: str) -> _AcquiredHandle | None:
        state = self._tiers.get(tier_name)
        if state is None:
            return None
        return await state.acquire()

    async def _release(
        self,
        tier_name: str,
        handle: _AcquiredHandle | None,
    ) -> None:
        if handle is None:
            return
        await handle.release()

    def snapshot(self) -> Dict[str, Dict[str, int]]:
        """Return a snapshot of inflight and queued counts for each tier."""

        return {
            name: state.snapshot()
            for name, state in self._tiers.items()
        }


__all__ = ["BackpressureController", "TierBackpressureSettings"]
