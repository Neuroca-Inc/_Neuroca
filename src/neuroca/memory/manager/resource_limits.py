"""Resource limit enforcement and watchdog helpers for memory tiers."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Dict

from neuroca.memory.exceptions import MemoryCapacityError

logger = logging.getLogger(__name__)


def _coerce_positive_int(value: Any) -> int | None:
    """Return ``value`` as a positive integer or ``None`` if invalid."""

    try:
        candidate = int(value)
    except (TypeError, ValueError):
        return None

    return candidate if candidate > 0 else None



def _coerce_ratio(value: Any) -> float | None:
    """Return ``value`` as a ratio in the ``(0, 1]`` range or ``None``."""

    try:
        candidate = float(value)
    except (TypeError, ValueError):
        return None

    if candidate <= 0:
        return None

    if candidate > 1:
        return 1.0

    return candidate



def _coerce_timeout(value: Any) -> float | None:
    """Return ``value`` as a positive timeout in seconds or ``None``."""

    try:
        candidate = float(value)
    except (TypeError, ValueError):
        return None

    return candidate if candidate > 0 else None



@dataclass(slots=True)
class TierResourceLimit:
    """Configuration describing the safeguards for a single tier."""

    name: str
    max_items: int | None = None
    soft_limit_ratio: float | None = 0.9
    overflow_policy: str = "reject"
    ingest_timeout_seconds: float | None = None
    eviction_timeout_seconds: float | None = 5.0
    max_eviction_attempts: int = 2

    @classmethod
    def from_config(cls, name: str, config: Dict[str, Any] | None) -> "TierResourceLimit":
        """Construct a limit object from raw configuration values."""

        config = dict(config or {})

        max_items = _coerce_positive_int(config.get("max_items"))
        soft_limit = _coerce_ratio(config.get("soft_limit_ratio", config.get("soft_limit")))
        overflow_policy = str(config.get("overflow_policy", "reject")).strip().lower()
        if overflow_policy not in {"reject", "evict"}:
            overflow_policy = "reject"

        ingest_timeout = _coerce_timeout(config.get("ingest_timeout_seconds"))
        eviction_timeout = _coerce_timeout(
            config.get("eviction_timeout_seconds", config.get("eviction_timeout"))
        )

        attempts = _coerce_positive_int(config.get("max_eviction_attempts")) or 2

        return cls(
            name=name,
            max_items=max_items,
            soft_limit_ratio=soft_limit,
            overflow_policy=overflow_policy,
            ingest_timeout_seconds=ingest_timeout,
            eviction_timeout_seconds=eviction_timeout,
            max_eviction_attempts=attempts,
        )

    @property
    def soft_limit_threshold(self) -> int | None:
        """Return the item threshold that should trigger early warnings."""

        if self.max_items is None or self.soft_limit_ratio is None:
            return None

        return max(0, int(self.max_items * self.soft_limit_ratio))

    @property
    def capacity_enforced(self) -> bool:
        """Return ``True`` when a hard item limit is configured."""

        return self.max_items is not None


class ResourceLimitWatchdog:
    """Enforce resource limits and guard against runaway ingestion."""

    def __init__(
        self,
        limits: Dict[str, TierResourceLimit] | None = None,
        *,
        log: logging.Logger | None = None,
    ) -> None:
        self._limits = dict(limits or {})
        self._log = log or logger.getChild("watchdog")
        self._locks: Dict[str, asyncio.Lock] = {}

    @classmethod
    def from_config(
        cls,
        config: Dict[str, Any] | None,
        *,
        log: logging.Logger | None = None,
    ) -> "ResourceLimitWatchdog":
        """Create a watchdog from the manager configuration payload."""

        config = config or {}
        default_section = config.get("default")
        default_config = dict(default_section) if isinstance(default_section, dict) else {}

        limits: Dict[str, TierResourceLimit] = {}
        for tier_name in ("stm", "mtm", "ltm"):
            tier_section = config.get(tier_name)
            tier_config = dict(default_config)
            if isinstance(tier_section, dict):
                tier_config.update(tier_section)
            limits[tier_name] = TierResourceLimit.from_config(tier_name, tier_config)

        return cls(limits, log=log)

    def limit_for(self, tier_name: str) -> TierResourceLimit | None:
        """Return the limit configuration for ``tier_name`` if present."""

        return self._limits.get(tier_name)

    def _lock_for(self, tier_name: str) -> asyncio.Lock:
        """Return the watchdog lock for ``tier_name`` creating it lazily."""

        if tier_name not in self._locks:
            self._locks[tier_name] = asyncio.Lock()
        return self._locks[tier_name]

    async def ensure_capacity(self, tier_name: str, tier: Any) -> None:
        """Ensure the tier can accept another item or trigger remediation."""

        limit = self.limit_for(tier_name)
        if limit is None or not limit.capacity_enforced:
            return

        lock = self._lock_for(tier_name)
        async with lock:
            current = await tier.count({})
            threshold = limit.soft_limit_threshold
            if threshold is not None and current >= threshold:
                self._log.debug(
                    "Tier %s nearing capacity (%s/%s)", tier_name, current, limit.max_items
                )

            if current < (limit.max_items or 0):
                return

            self._log.warning(
                "Tier %s reached configured capacity (%s/%s) with %s policy",  # noqa: G004
                tier_name,
                current,
                limit.max_items,
                limit.overflow_policy,
            )

            if limit.overflow_policy == "evict":
                await self._attempt_evictions(tier_name, tier, limit, current)
                post_cleanup = await tier.count({})
                if post_cleanup < (limit.max_items or 0):
                    return

            raise MemoryCapacityError(
                f"{tier_name} tier is at capacity ({current}/{limit.max_items})"
            )

    async def _attempt_evictions(
        self,
        tier_name: str,
        tier: Any,
        limit: TierResourceLimit,
        starting_count: int,
    ) -> None:
        """Attempt to free capacity using the tier's cleanup hook."""

        cleanup = getattr(tier, "cleanup", None)
        if cleanup is None:
            self._log.error("Tier %s does not implement cleanup; cannot evict", tier_name)
            return

        attempts = max(1, limit.max_eviction_attempts)
        for attempt in range(1, attempts + 1):
            try:
                cleanup_coro = cleanup()
                if asyncio.iscoroutine(cleanup_coro):
                    if limit.eviction_timeout_seconds:
                        removed = await asyncio.wait_for(
                            cleanup_coro, timeout=limit.eviction_timeout_seconds
                        )
                    else:
                        removed = await cleanup_coro
                else:  # pragma: no cover - defensive fallback
                    removed = cleanup_coro
            except asyncio.TimeoutError:
                self._log.error(
                    "Cleanup attempt %s for tier %s timed out after %.2fs",
                    attempt,
                    tier_name,
                    limit.eviction_timeout_seconds,
                )
                removed = 0
            except Exception as exc:  # noqa: BLE001
                self._log.exception(
                    "Cleanup attempt %s for tier %s failed due to %s",
                    attempt,
                    tier_name,
                    exc,
                )
                removed = 0

            removed_int = _coerce_positive_int(removed) or 0
            if removed_int:
                self._log.info(
                    "Tier %s eviction attempt %s removed %s items (starting count %s)",
                    tier_name,
                    attempt,
                    removed_int,
                    starting_count,
                )
            else:
                self._log.debug(
                    "Tier %s eviction attempt %s removed no items", tier_name, attempt
                )

            current = await tier.count({})
            if current < (limit.max_items or 0):
                return

    async def store(self, tier_name: str, tier: Any, payload: Any) -> Any:
        """Store ``payload`` in ``tier`` honouring configured timeouts."""

        limit = self.limit_for(tier_name)
        store_coro = tier.store(payload)

        if limit is None or not limit.ingest_timeout_seconds:
            return await store_coro

        try:
            return await asyncio.wait_for(store_coro, timeout=limit.ingest_timeout_seconds)
        except asyncio.TimeoutError:
            self._log.error(
                "Timed out storing memory in tier %s after %.2fs",
                tier_name,
                limit.ingest_timeout_seconds,
            )
            raise


__all__ = [
    "TierResourceLimit",
    "ResourceLimitWatchdog",
]
